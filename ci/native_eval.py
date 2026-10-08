"""Opt-in app-server transport with per-turn, same-process native inventory.

This profile is deliberately distinct from historical exec evaluations.
Authentication is copied only into a private disposable home, never changed in
its source location, and is never included in reports or RPC trace artifacts.
"""
from __future__ import annotations

import csv
import io
import json
import os
import queue
import re
import subprocess
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

if __package__:
    from . import probe_eval_isolation as probe
else:
    import probe_eval_isolation as probe

evals = probe.evals
PROFILE = "native-runtime-v1"


def load_auth(path: Path) -> dict:
    try:
        auth = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise probe.ProbeError("Cannot load native authentication source") from exc
    if (not isinstance(auth, dict) or auth.get("auth_mode") != "chatgpt"
            or not isinstance(auth.get("tokens"), dict)
            or not all(isinstance(auth["tokens"].get(key), str) and auth["tokens"][key]
                       for key in ("access_token", "account_id"))):
        raise probe.ProbeError("Native runtime currently requires an existing ChatGPT login")
    return auth


def auth_identity(auth: dict) -> str:
    # Account identity, NOT a hash of a credential/token.
    return probe.digest({"mode": auth["auth_mode"], "account": auth["tokens"]["account_id"]})


def private_permissions(home: Path) -> None:
    if os.name != "nt":
        home.chmod(0o700)
        return
    try:
        result = subprocess.run(
            ["whoami", "/user", "/fo", "csv", "/nh"], capture_output=True,
            text=True, encoding="utf-8", check=True, timeout=10,
        )
        sid = next(csv.reader(io.StringIO(result.stdout)))[1]
        if not re.fullmatch(r"S-\d+(?:-\d+)+", sid):
            raise ValueError("Missing SID")
        subprocess.run(
            ["icacls", str(home), "/inheritance:r", "/grant:r", f"*{sid}:(OI)(CI)F"],
            capture_output=True, check=True, timeout=10,
        )
    except (OSError, ValueError, IndexError, StopIteration, subprocess.SubprocessError) as exc:
        raise probe.ProbeError("Cannot protect disposable native credentials") from exc


@contextmanager
def authenticated_home(auth: dict):
    with tempfile.TemporaryDirectory(prefix="bsp-runtime-home-") as directory:
        home = Path(directory).resolve()
        private_permissions(home)  # Fail before writing any credential.
        descriptor = os.open(home / "auth.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(auth, stream)
        yield home


def redact(value: object, secrets: list[str], home: Path) -> object:
    if isinstance(value, dict):
        return {key: redact(item, secrets, home) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item, secrets, home) for item in value]
    if isinstance(value, str):
        for secret in sorted(secrets, key=len, reverse=True):
            if secret:
                value = value.replace(secret, "[REDACTED]")
        value = re.sub(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", "[REDACTED-JWT]", value)
        return value.replace(str(home), "$RUNTIME_CODEX_HOME")
    return value


def auth_secrets(auth: dict) -> list[str]:
    return [value for key, value in auth.get("tokens", {}).items()
            if key != "account_id" and isinstance(value, str)]


def normalized_item(raw: dict) -> dict | None:
    if raw.get("type") == "commandExecution":
        if not isinstance(raw.get("command"), str):
            raise probe.ProbeError("Malformed native command item")
        return {"type": "item.completed", "item": {
            "id": raw.get("id"), "type": "command_execution", "command": raw["command"],
            "exit_code": raw.get("exitCode"), "aggregated_output": raw.get("aggregatedOutput") or "",
        }}
    if raw.get("type") == "agentMessage" and raw.get("phase") != "commentary":
        if not isinstance(raw.get("text"), str):
            raise probe.ProbeError("Malformed native answer item")
        return {"type": "item.completed", "item": {
            "id": raw.get("id"), "type": "agent_message", "text": raw["text"],
        }}
    return None


def phase_inventory_reasons(snapshot: dict, phase: str, target: Path, source_sha256: str) -> list[str]:
    # Enforce phase-local safety before submitting any task. Cross-phase equality
    # is checked by report_inventory_reasons after actual RED/GREEN runs.
    if phase == "red":
        return ["RED discovers BSP or other project skills"] if any(
            item["name"].casefold() == "bsp" or item["scope"] == "repo" for item in snapshot["skills"]
        ) else []
    control = {**snapshot, "skills": [item for item in snapshot["skills"]
                                       if probe.normalized_path(item["path"]) != probe.normalized_path(str(target / "SKILL.md"))]}
    return probe.compare_snapshots(control, snapshot, control, target, "bsp", source_sha256)


def collect_turn(client, thread_id: str, task: str, timeout: int, *, events=None, notifications=None) -> tuple[list[dict], list[dict], dict, str]:
    """Collect only the requested turn, including events arriving before RPC ack."""
    result = client.call("turn/start", {"threadId": thread_id, "input": [{"type": "text", "text": task}]})
    turn_id = result.get("turn", {}).get("id")
    if not isinstance(turn_id, str) or not turn_id:
        raise probe.ProbeError("Native turn/start omitted turn identity")
    deadline = time.monotonic() + timeout
    notifications = [] if notifications is None else notifications
    events = [] if events is None else events
    usage = {}
    completed_items = set()
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise probe.ProbeError("Native model turn timeout")
        message = client.next_notification(remaining)
        method = message.get("method")
        params = message.get("params", {})
        if params.get("threadId") != thread_id:
            continue
        if method == "turn/completed":
            turn = params.get("turn", {})
            if turn.get("id") != turn_id:
                continue
            # Some servers include final items only in the completion payload.
            for item in turn.get("items", []):
                if item.get("id") not in completed_items:
                    normalized = normalized_item(item)
                    if normalized:
                        events.append(normalized)
            notifications.append(message)
            events.append({"type": "turn.completed", "usage": usage})
            return events, notifications, turn, turn_id
        if params.get("turnId") != turn_id:
            continue
        if method == "item/completed":
            raw = params.get("item", {})
            if raw.get("id") not in completed_items:
                normalized = normalized_item(raw)
                if normalized:
                    events.append(normalized)
                completed_items.add(raw.get("id"))
            notifications.append(message)
        elif method == "thread/tokenUsage/updated":
            total = params.get("tokenUsage", {}).get("total", {})
            usage = {key: total.get(native_key, 0) for key, native_key in (
                ("input_tokens", "inputTokens"), ("cached_input_tokens", "cachedInputTokens"),
                ("output_tokens", "outputTokens"), ("reasoning_output_tokens", "reasoningOutputTokens"),
            )}
            notifications.append(message)
        elif method == "error":
            notifications.append(message)


def runtime_command(cdx, workdir, model, effort) -> list[str]:
    command = probe.audit_command(cdx, workdir, model, effort)
    command.extend(["-c", "features.multi_agent=false", "-c", "features.goals=false"])
    return command


def run_native(cdx, case, workdir, artifact_dir, phase, run_number, model, effort,
               timeout, skill_name, home, source_sha256, identity_sha256) -> dict:
    command = runtime_command(cdx, workdir, model, effort)
    environment = probe.audit_environment(home)
    started = time.monotonic()
    events, notifications, before, after = [], [], None, None
    thread_id, turn_id, error = None, None, ""
    reasons = []
    returncode, timed_out = 0, False
    client = None
    original_secrets = []
    try:
        active_auth = load_auth(home / "auth.json")
        original_secrets = auth_secrets(active_auth)
        if auth_identity(active_auth) != identity_sha256:
            reasons.append("Native authentication source identity changed")
            raise probe.ProbeError("Native authentication identity rejected before model turn")
        client = probe.NativeClient(command, workdir, environment, min(timeout, 60))
        initialized = probe.initialize_native(client, home)
        account = client.call("account/read", {"refreshToken": False})
        if not isinstance(account.get("account"), dict) or account["account"].get("type") != "chatgpt":
            raise probe.ProbeError("Native runtime did not load ChatGPT authentication")
        before, thread = probe.capture_snapshot(client, workdir, home, environment, initialized)
        before["auth_identity_sha256"] = identity_sha256
        before["native_account_sha256"] = probe.digest(account)
        thread_id = thread.get("thread", {}).get("id")
        if not isinstance(thread_id, str) or not thread_id:
            raise probe.ProbeError("Native thread/start omitted thread identity")
        reasons = phase_inventory_reasons(before, phase, workdir / ".agents/skills/bsp", source_sha256)
        if reasons:
            raise probe.ProbeError("Native phase inventory rejected before model turn")
        events, notifications, turn, turn_id = collect_turn(
            client, thread_id, case.task, timeout, events=events, notifications=notifications,
        )
        if turn.get("status") != "completed" or turn.get("error"):
            returncode = 1
            error = str((turn.get("error") or {}).get("message") or "Native turn failed")
        after, _ = probe.capture_snapshot(client, workdir, home, environment, initialized, thread=thread)
        after["auth_identity_sha256"] = identity_sha256
        after["native_account_sha256"] = probe.digest(client.call("account/read", {"refreshToken": False}))
        if before != after:
            reasons.append("Native environment drifted during model turn")
    except (probe.ProbeError, OSError, ValueError, queue.Empty, subprocess.SubprocessError) as exc:
        returncode = 1
        error = str(exc) if isinstance(exc, probe.ProbeError) else "Native transport failed"
        rpc_error = getattr(client, "last_rpc_error", None)
        if isinstance(rpc_error, dict) and isinstance(rpc_error.get("message"), str):
            error += ": " + rpc_error["message"]
        timed_out = "timeout" in error.lower()
        if before is None or after is None:
            reasons.append("Same-process native inventory is incomplete")
    finally:
        if client is not None:
            try:
                client.close()
            except (OSError, subprocess.SubprocessError):
                returncode = 1
                error = "Native process cleanup failed"
    try:
        secrets = original_secrets + auth_secrets(load_auth(home / "auth.json"))
    except probe.ProbeError:
        secrets = original_secrets
    # Preserve original secrets too: managed refresh can replace private auth.json.
    events = redact(events, secrets, home)
    notifications = redact(notifications, secrets, home)
    error = redact(error, secrets, home)
    response = evals.final_message(events)
    prefix = f"{case.id}.{phase}.{run_number}"
    (artifact_dir / f"{prefix}.jsonl").write_text(
        "".join(json.dumps(event, ensure_ascii=False) + "\n" for event in events), encoding="utf-8",
    )
    (artifact_dir / f"{prefix}.native.jsonl").write_text(
        "".join(json.dumps(event, ensure_ascii=False) + "\n" for event in notifications), encoding="utf-8",
    )
    (artifact_dir / f"{prefix}.response.md").write_text(response, encoding="utf-8")
    (artifact_dir / f"{prefix}.stderr.txt").write_text(error, encoding="utf-8")
    activation = evals.skill_activation_evidence(events, skill_name)
    reference = evals.skill_activation_evidence(events, skill_name, case.reference) if case.should_trigger and case.reference else []
    return {
        "returncode": returncode, "timed_out": timed_out,
        "tool_policy_blocked": any("blocked by policy" in event.get("item", {}).get("aggregated_output", "") for event in events),
        "tool_output_decode_errors": evals.tool_output_decode_errors(events),
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "usage": evals.usage_from_events(events), "response": response,
        "skill_activated": bool(activation), "activation_evidence": activation,
        "expected_reference_read": bool(reference), "reference_evidence": reference,
        "json_events": len(events), "stdout_noise": [], "stderr_tail": error[-4000:],
        "native_isolation_reasons": reasons,
        "native_inventory": {"profile": PROFILE,
                             "launcher_pid": getattr(getattr(client, "process", None), "pid", None),
                             "thread_id": thread_id, "turn_id": turn_id,
                             "before": before, "after": after},
    }


def restored_snapshot(cdx, workdir, home, model, effort, timeout, identity_sha256) -> dict:
    if auth_identity(load_auth(home / "auth.json")) != identity_sha256:
        raise probe.ProbeError("Post-cleanup authentication identity changed")
    environment = probe.audit_environment(home)
    client = probe.NativeClient(runtime_command(cdx, workdir, model, effort), workdir, environment, min(timeout, 60))
    try:
        initialized = probe.initialize_native(client, home)
        account = client.call("account/read", {"refreshToken": False})
        if not isinstance(account.get("account"), dict) or account["account"].get("type") != "chatgpt":
            raise probe.ProbeError("Post-cleanup native authentication is missing")
        snapshot, _ = probe.capture_snapshot(client, workdir, home, environment, initialized)
        snapshot["auth_identity_sha256"] = identity_sha256
        snapshot["native_account_sha256"] = probe.digest(account)
        return snapshot
    finally:
        client.close()


def report_inventory_reasons(report: dict, target: Path) -> list[str]:
    executions = [(phase, run) for phase in ("red", "green")
                  for case_runs in report.get("phases", {}).get(phase, {}).get("run_matrix", {}).values()
                  for run in case_runs if isinstance(run, dict)]
    controls = [run.get("native_inventory", {}).get("before") for phase, run in executions if phase == "red"]
    control = next((snapshot for snapshot in controls if isinstance(snapshot, dict)), None)
    if control is None:
        return ["No actual RED runtime inventory"]
    reasons = []
    if report.get("native_warmup_red") != control:
        reasons.append("Bootstrap RED inventory differs from actual model runs")
    restored = report.get("native_restored_red")
    if not isinstance(restored, dict):
        reasons.append("Missing post-cleanup RED inventory")
        restored = control
    for key in ("auth_identity_sha256", "native_account_sha256"):
        if not control.get(key) or restored.get(key) != control[key]:
            reasons.append("Post-cleanup authentication identity differs or is missing")
    for phase, run in executions:
        inventory = run.get("native_inventory", {})
        before, after = inventory.get("before"), inventory.get("after")
        if (inventory.get("profile") != PROFILE
                or not isinstance(inventory.get("launcher_pid"), int) or inventory["launcher_pid"] <= 0
                or not inventory.get("thread_id") or not inventory.get("turn_id")
                or not isinstance(before, dict) or before != after):
            reasons.append("Missing or drifting inventory bound to a native turn")
            continue
        if phase == "red" and before != control:
            reasons.append("Actual RED environments differ")
        elif phase == "green":
            reasons.extend(probe.compare_snapshots(control, before, restored, target, "bsp", report["skill_sha256"]))
            for key in ("auth_identity_sha256", "native_account_sha256"):
                if before.get(key) != control.get(key):
                    reasons.append("Actual RED/GREEN authentication identity differs")
    if not any(phase == "green" for phase, _ in executions):
        reasons.append("No actual GREEN runtime inventory")
    return sorted(set(reasons))
