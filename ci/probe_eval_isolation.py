#!/usr/bin/env python3
"""Audit native RED/GREEN catalogs without model calls or global configuration writes.

This is a preflight, NOT proof of the environment used by `codex exec`.
The native app-server uses a disposable, credential-free CODEX_HOME and an
explicit diagnostic profile. Historical exec reports cannot inherit its PASS.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import queue
import signal
import stat
import subprocess
import tempfile
import threading
from pathlib import Path

if __package__:
    from . import run_skill_evals as evals
else:
    import run_skill_evals as evals


PROFILE = "native-preflight-clean-home-v1"
ENVIRONMENT_KEYS = frozenset({
    "PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "COMSPEC", "TEMP", "TMP", "TMPDIR",
    "HOME", "USERPROFILE", "HOMEDRIVE", "HOMEPATH", "APPDATA", "LOCALAPPDATA",
    "PROGRAMDATA", "PROGRAMFILES", "PROGRAMFILES(X86)", "PROGRAMW6432",
    "USER", "LOGNAME", "USERNAME", "USERDOMAIN", "OS", "PROCESSOR_ARCHITECTURE",
    "NUMBER_OF_PROCESSORS", "LANG", "LC_ALL", "LC_CTYPE", "TERM", "TZ",
})
DISABLED_FEATURES = (
    "plugins", "remote_plugin", "apps", "hooks", "memories",
    "skill_mcp_dependency_install", "shell_snapshot",
)
LIMITATION = (
    "Independent app-server preflight with a disposable credential-free CODEX_HOME; "
    "not an inventory of actual exec processes, not a behavioral baseline, "
    "and not proof of isolation for historical reports."
)


class ProbeError(RuntimeError):
    """Fail closed when native inventory is unavailable or inconsistent."""


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")).hexdigest()


def normalized_path(value: str) -> str:
    return os.path.normcase(str(Path(value).resolve()))


def is_linked(path: Path) -> bool:
    if path.is_symlink() or getattr(path, "is_junction", lambda: False)():
        return True
    # Path.is_junction is unavailable before Python 3.12. Refuse other Windows
    # reparse points as well, rather than risk copying through a linked parent.
    if os.name == "nt":
        try:
            return bool(getattr(path.lstat(), "st_file_attributes", 0)
                        & stat.FILE_ATTRIBUTE_REPARSE_POINT)
        except FileNotFoundError:
            pass
    return False


def audit_environment(home: Path, inherited: dict | None = None) -> dict:
    """Do not forward credentials, provider overrides or host integration tokens."""
    inherited = os.environ if inherited is None else inherited
    return {
        **{key: value for key, value in inherited.items() if key.upper() in ENVIRONMENT_KEYS},
        "CODEX_HOME": str(home), "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1",
    }


def audit_command(cdx: str, workdir: Path, model: str, effort: str | None) -> list[str]:
    """Reuse exec's explicit -c overrides, but identify the different profile."""
    case = evals.EvalCase("inventory", "No model turn", None, False, False, (), (), ())
    exec_command = evals.build_cdx_command(cdx, case, workdir, model, effort)
    command = [cdx, "app-server", "--stdio"]
    for index, argument in enumerate(exec_command):
        if argument == "-c":
            command.extend(["-c", exec_command[index + 1]])
    command.extend([
        "-c", "model=" + json.dumps(model),
        "-c", 'sandbox_mode="read-only"',
        "-c", 'approval_policy="never"',
        "-c", 'web_search="disabled"',
    ])
    for feature in DISABLED_FEATURES:
        command.extend(["-c", f"features.{feature}=false"])
    return command


class NativeClient:
    """Small bounded stdio RPC client; never starts a model turn."""

    def __init__(self, command: list[str], workdir: Path, environment: dict, timeout: int):
        self.timeout = timeout
        self.messages: queue.Queue = queue.Queue()
        self.notifications: list[dict] = []
        self.sequence = 0
        self.process = subprocess.Popen(
            command, cwd=workdir, env=environment,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="strict",
            start_new_session=os.name != "nt",
        )
        self.readers = [
            threading.Thread(target=self._read_stdout, daemon=True),
            threading.Thread(target=self._drain_stderr, daemon=True),
        ]
        for reader in self.readers:
            reader.start()

    def _read_stdout(self) -> None:
        try:
            for line in self.process.stdout:
                message = json.loads(line)
                if not isinstance(message, dict):
                    raise ValueError("Not an RPC object")
                self.messages.put(message)
        except (ValueError, OSError):
            self.messages.put({"probe_error": "Malformed native RPC output"})
        finally:
            self.messages.put({"probe_error": "Native RPC process closed stdout"})

    def _drain_stderr(self) -> None:
        # Config/provider errors can contain credentials. Never persist raw stderr.
        try:
            while self.process.stderr.read(4096):
                pass
        except (OSError, UnicodeError):
            pass

    def send(self, message: dict) -> None:
        try:
            self.process.stdin.write(json.dumps(message) + "\n")
            self.process.stdin.flush()
        except (OSError, ValueError) as exc:
            raise ProbeError("Cannot write native RPC request") from exc

    def call(self, method: str, params: dict) -> dict:
        import time
        self.sequence += 1
        request_id = self.sequence
        self.send({"id": request_id, "method": method, "params": params})
        deadline = time.monotonic() + self.timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ProbeError(f"Native RPC timeout: {method}")
            try:
                message = self.messages.get(timeout=remaining)
            except queue.Empty as exc:
                raise ProbeError(f"Native RPC timeout: {method}") from exc
            if "probe_error" in message:
                raise ProbeError(message["probe_error"])
            if message.get("id") == request_id and "method" not in message:
                if "error" in message:
                    # Do not copy arbitrary native error messages into reports.
                    raise ProbeError(f"Native RPC rejected {method}")
                result = message.get("result")
                if not isinstance(result, dict):
                    raise ProbeError(f"Missing native RPC result: {method}")
                return result
            if "id" in message and "method" in message:
                self.send({"id": message["id"], "error": {
                    "code": -32601, "message": "No interactive requests in inventory preflight",
                }})
            elif "method" in message and "id" not in message:
                self.notifications.append(message)
            else:
                raise ProbeError("Malformed native RPC message")

    def next_notification(self, timeout: int) -> dict:
        import time
        if self.notifications:
            return self.notifications.pop(0)
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ProbeError("Native notification timeout")
            try:
                message = self.messages.get(timeout=remaining)
            except queue.Empty as exc:
                raise ProbeError("Native notification timeout") from exc
            if "probe_error" in message:
                raise ProbeError(message["probe_error"])
            if "id" in message and "method" in message:
                self.send({"id": message["id"], "error": {
                    "code": -32601, "message": "No interactive requests in inventory preflight",
                }})
                raise ProbeError("Unexpected native server request")
            if "method" in message and "id" not in message:
                return message
            raise ProbeError("Malformed native RPC message")

    def close(self) -> None:
        try:
            self.process.stdin.close()
            self.process.wait(timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/PID", str(self.process.pid), "/T", "/F"],
                    capture_output=True, timeout=10, check=False,
                )
            else:
                try:
                    os.killpg(self.process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            self.process.wait(timeout=10)
        finally:
            for reader in self.readers:
                reader.join(timeout=1)
            self.process.stdout.close()
            self.process.stderr.close()


def skill_record(raw: dict, home: Path) -> dict:
    required = {"name": str, "path": str, "scope": str, "enabled": bool}
    if not isinstance(raw, dict) or any(not isinstance(raw.get(key), kind) for key, kind in required.items()):
        raise ProbeError("Malformed native skill metadata")
    path = Path(raw["path"]).resolve()
    if not path.is_file():
        raise ProbeError("Catalog skill file is not readable")
    root = path.parent
    if path.is_relative_to(home):
        display = "$AUDIT_CODEX_HOME/" + path.relative_to(home).as_posix()
    else:
        display = str(path)
    # Metadata may contain dependency URLs; keep only a digest, never raw values.
    # Paths embedded in nested metadata (for example interface icon paths) must
    # not make system-skill fingerprints depend on the temporary CODEX_HOME.
    home_text = str(home.resolve())
    def normalize_metadata(value):
        if isinstance(value, str):
            for prefix in (home_text, home_text.replace("\\", "/")):
                if value == prefix or value.startswith(prefix + "/") or value.startswith(prefix + "\\"):
                    return "$AUDIT_CODEX_HOME" + value[len(prefix):]
            return value
        if isinstance(value, list):
            return [normalize_metadata(item) for item in value]
        if isinstance(value, dict):
            return {key: normalize_metadata(item) for key, item in value.items()}
        return value
    metadata = normalize_metadata({**raw, "path": display})
    return {
        "name": raw["name"], "path": display, "scope": raw["scope"],
        "enabled": raw["enabled"], "plugin_id": raw.get("pluginId"),
        "metadata_sha256": digest(metadata),
        "content_sha256": evals.skill_sha256(root),
    }


def initialize_native(client: NativeClient, home: Path) -> dict:
    initialized = client.call("initialize", {
        "clientInfo": {"name": "bsp-isolation-preflight", "version": "1"},
        "capabilities": {"experimentalApi": True},
    })
    if normalized_path(initialized.get("codexHome", "")) != normalized_path(str(home)):
        raise ProbeError("Native process did not use disposable CODEX_HOME")
    client.send({"method": "initialized"})
    return initialized


def capture_snapshot(client: NativeClient, workdir: Path, home: Path,
                     environment: dict, initialized: dict, thread: dict | None = None) -> tuple[dict, dict]:
        config_result = client.call("config/read", {"cwd": str(workdir), "includeLayers": True})
        config = config_result.get("config")
        layers = config_result.get("layers")
        if not isinstance(config, dict) or not isinstance(layers, list):
            raise ProbeError("Native configuration inventory is incomplete")
        if any(not isinstance(layer, dict) or not isinstance(layer.get("name"), dict)
               for layer in layers):
            raise ProbeError("Malformed native configuration layers")
        if any(layer["name"].get("type") == "project" and not layer.get("disabledReason")
               for layer in layers):
            raise ProbeError("Consumer root loads project configuration")
        if config.get("mcp_servers"):
            raise ProbeError("Consumer profile exposes MCP servers")
        features = config.get("features", {})
        if not isinstance(features, dict) or any(features.get(feature) is not False for feature in DISABLED_FEATURES):
            raise ProbeError("Native process did not apply diagnostic feature restrictions")
        catalog = client.call("skills/list", {"cwds": [str(workdir)], "forceReload": True})
        entries = catalog.get("data")
        if (not isinstance(entries, list) or len(entries) != 1
                or not isinstance(entries[0], dict)
                or normalized_path(entries[0].get("cwd", "")) != normalized_path(str(workdir))
                or entries[0].get("errors") != []
                or not isinstance(entries[0].get("skills"), list)):
            raise ProbeError("Native skill catalog is incomplete or has discovery errors")
        skills = sorted(
            (skill_record(raw, home) for raw in entries[0]["skills"]),
            key=lambda record: (record["path"], record["name"]),
        )
        if len({record["path"] for record in skills}) != len(skills):
            raise ProbeError("Duplicate paths in native skill catalog")
        plugins = client.call("plugin/list", {
            "cwds": [str(workdir)], "forceRefetch": False, "marketplaceKinds": ["local"],
        })
        if (not isinstance(plugins.get("marketplaces"), list)
                or plugins.get("marketplaceLoadErrors") != []):
            raise ProbeError("Native plugin inventory is incomplete or has load errors")
        # In this profile plugin execution is disabled. Do not mistake a local
        # marketplace listing for a complete inventory of enabled remote plugins.
        if plugins["marketplaces"]:
            raise ProbeError("Disabled-plugin profile unexpectedly exposes marketplaces")
        if thread is None:
            thread = client.call("thread/start", {
                "cwd": str(workdir), "ephemeral": True,
                "sandbox": "read-only", "approvalPolicy": "never",
            })
        if (not isinstance(thread, dict)
                or normalized_path(thread.get("cwd", "")) != normalized_path(str(workdir))
                or not isinstance(thread.get("instructionSources"), list)
                or thread["instructionSources"]
                or not isinstance(thread.get("disabledPluginIds"), list)):
            raise ProbeError("Consumer thread loads instruction files or lacks source inventory")
        if (thread.get("approvalPolicy") != "never"
                or not isinstance(thread.get("sandbox"), dict)
                or thread["sandbox"].get("type") != "readOnly"):
            raise ProbeError("Native thread did not apply read-only diagnostic permissions")
        snapshot = {
            "user_agent": initialized.get("userAgent"),
            "environment_policy": "os-paths-only-v1",
            "environment_names": sorted(environment),
            "environment_paths_sha256": digest({
                key: environment.get(key) for key in (
                    "PATH", "PATHEXT", "SYSTEMROOT", "COMSPEC", "HOME", "USERPROFILE",
                    "PYTHONUTF8", "PYTHONIOENCODING", "LANG", "LC_ALL", "TERM",
                )
            }),
            "config_sha256": digest(config),
            "config_layers": [{"source_type": layer.get("name", {}).get("type"),
                               "sha256": digest(layer.get("config"))}
                              for layer in layers],
            "skills": skills,
            "plugins_enabled": False,
            "plugin_inventory_sha256": digest(plugins),
            "instruction_sources": [],
            "thread_profile": {key: thread.get(key) for key in (
                "model", "modelProvider", "reasoningEffort", "approvalPolicy", "sandbox",
                "disabledPluginIds",
            )},
        }
        return snapshot, thread


def native_snapshot(command: list[str], workdir: Path, home: Path, timeout: int) -> dict:
    environment = audit_environment(home)
    client = NativeClient(command, workdir, environment, timeout)
    try:
        initialized = initialize_native(client, home)
        snapshot, _thread = capture_snapshot(
            client, workdir, home, environment, initialized
        )
        return snapshot
    finally:
        client.close()


def compare_snapshots(red: dict, green: dict, restored: dict, target: Path,
                      skill_name: str, source_sha256: str) -> list[str]:
    """Only the one enabled repo-scoped staged skill may be added."""
    reasons = []
    target_path = normalized_path(str(target / "SKILL.md"))
    for label, snapshot in (("RED", red), ("restored RED", restored)):
        if any(record["name"].casefold() == skill_name.casefold() for record in snapshot["skills"]):
            reasons.append(f"{label} discovers {skill_name}")
        if any(record["scope"] == "repo" for record in snapshot["skills"]):
            reasons.append(f"{label} discovers other project skills")
    staged = [record for record in green["skills"]
              if normalized_path(record["path"]) == target_path]
    if (len(staged) != 1 or staged[0]["name"] != skill_name
            or staged[0]["scope"] != "repo" or staged[0]["enabled"] is not True
            or staged[0]["plugin_id"] is not None
            or staged[0]["content_sha256"] != source_sha256):
        reasons.append("GREEN must discover exactly the enabled staged BSP bytes")
    other_green = [record for record in green["skills"]
                   if normalized_path(record["path"]) != target_path]
    if other_green != red["skills"]:
        reasons.append("GREEN changes skills other than staged BSP")
    if restored["skills"] != red["skills"]:
        reasons.append("Catalog changes after staged BSP cleanup")
    for key in ("user_agent", "environment_policy", "environment_names", "environment_paths_sha256",
                "config_sha256", "config_layers", "plugins_enabled",
                "plugin_inventory_sha256", "instruction_sources", "thread_profile"):
        if green[key] != red[key] or restored[key] != red[key]:
            reasons.append(f"Native environment differs: {key}")
    return reasons


def validate_workdir(workdir: Path, output: Path) -> None:
    repo = evals.REPO_ROOT.resolve()
    if workdir.is_relative_to(repo) or repo.is_relative_to(workdir):
        raise ProbeError("Use a separate consumer Git root outside the development repository")
    if output.is_relative_to(workdir):
        raise ProbeError("Store audit output outside the consumer root")
    try:
        result = subprocess.run(
            ["git", "-C", str(workdir), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, encoding="utf-8", check=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ProbeError("Consumer directory must be an existing Git root") from exc
    if normalized_path(result.stdout.strip()) != normalized_path(str(workdir)):
        raise ProbeError("Consumer directory must be the Git root, not a subdirectory")
    if any((workdir / path).exists() for path in ("bsp3111_md", "bsp321_md", "src/cf")):
        raise ProbeError("Consumer root contains developer BSP sources")


def run_audit(skill: Path, workdir: Path, home: Path, command: list[str], timeout: int,
              snapshot=native_snapshot) -> dict:
    name = evals.validate_skill(skill)
    if name != "bsp":
        raise ProbeError("Only the umbrella bsp skill is supported")
    target = workdir / ".agents" / "skills" / name
    if target.exists() or is_linked(target):
        raise ProbeError("Refusing to overwrite existing staged BSP")
    if is_linked(target.parent) or is_linked(target.parent.parent):
        raise ProbeError("Refusing to stage through linked .agents/skills directories")
    source_sha256 = evals.skill_sha256(skill)
    red = snapshot(command, workdir, home, timeout)
    # Fail before creating GREEN if the control environment is contaminated.
    if any(record["name"].casefold() == name or record["scope"] == "repo"
           for record in red["skills"]):
        raise ProbeError("RED already discovers BSP or other project skills")
    with evals.staged_skill(skill, target):
        green = snapshot(command, workdir, home, timeout)
    restored = snapshot(command, workdir, home, timeout)
    reasons = compare_snapshots(red, green, restored, target, name, source_sha256)
    return {
        "snapshots": {"red": red, "green": green, "restored_red": restored},
        "skill_sha256": source_sha256,
        "catalog_gate": {"passed": not reasons, "reasons": reasons},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", required=True, help="Separate consumer Git root")
    parser.add_argument("--output", required=True, help="New report path outside consumer root")
    parser.add_argument("--skill", default=str(evals.DEFAULT_SKILL))
    parser.add_argument("--cdx", default="cdx")
    parser.add_argument("--model", default=evals.DEFAULT_MODEL)
    parser.add_argument("--reasoning-effort", choices=("low", "medium", "high", "xhigh"))
    parser.add_argument("--timeout", type=int, default=60, help="Seconds per native RPC request")
    args = parser.parse_args()
    requested_output = Path(args.output).absolute()
    output = requested_output.resolve()
    report = {
        "schema_version": 1, "profile": PROFILE, "model_calls": 0,
        "exec_runtime_isolation_proven": False, "limitation": LIMITATION,
        "probe_sha256": evals.file_sha256(Path(__file__)),
        "runner_sha256": evals.file_sha256(Path(evals.__file__)),
        "complete": False, "catalog_gate": {"passed": False, "reasons": []},
    }
    created_output = False
    try:
        if is_linked(requested_output):
            raise ProbeError("Refusing to write through a linked report path")
        if args.timeout < 1:
            raise ProbeError("--timeout must be at least 1")
        workdir = Path(args.dir).resolve()
        validate_workdir(workdir, output)
        cdx = evals.resolve_cdx(args.cdx)
        command = audit_command(cdx, workdir, args.model, args.reasoning_effort)
        output.parent.mkdir(parents=True, exist_ok=True)
        # Do not overwrite a previous audit, including dangling symlinks.
        with output.open("x", encoding="utf-8"):
            pass
        created_output = True
        report.update({"workdir": str(workdir), "launcher": cdx, "command": command})
        with tempfile.TemporaryDirectory(prefix="bsp-audit-home-") as directory:
            report.update(run_audit(
                Path(args.skill).resolve(), workdir, Path(directory).resolve(), command, args.timeout,
            ))
        report["complete"] = True
        evals.atomic_write_json(output, report)
        print(f"Native catalog preflight: {'PASS' if report['catalog_gate']['passed'] else 'FAIL'}")
        print(LIMITATION)
        print(f"Report: {output}")
        raise SystemExit(0 if report["catalog_gate"]["passed"] else 1)
    except (ProbeError, evals.EvalError, OSError, subprocess.SubprocessError) as exc:
        # Error strings are our own setup messages, not raw config/RPC payloads.
        reason = str(exc) if isinstance(exc, (ProbeError, evals.EvalError)) else "File/process setup error"
        report["catalog_gate"] = {"passed": False, "reasons": [reason]}
        if created_output:
            evals.atomic_write_json(output, report)
        print(f"ERROR: {reason}")
        raise SystemExit(2)


if __name__ == "__main__":
    main()
