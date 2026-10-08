import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ci import native_eval as native
from ci import run_skill_evals as runner


class FakeClient:
    def __init__(self, notifications):
        self.notifications = list(notifications)
        self.requests = []
        self.process = type("Process", (), {"pid": 123})()
    def call(self, method, params):
        self.requests.append((method, params))
        if method == "turn/start":
            return {"turn": {"id": "turn-1"}}
        if method == "account/read":
            return {"account": {"type": "chatgpt", "email": "private@example.test"}}
        raise AssertionError(method)
    def next_notification(self, timeout):
        return self.notifications.pop(0)
    def close(self):
        pass


def notification(method, params):
    return {"method": method, "params": {"threadId": "thread-1", **params}}


def completed_turn(items=None):
    return notification("turn/completed", {"turn": {"id": "turn-1", "status": "completed", "items": items or []}})


class NativeTransportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.auth = {"auth_mode": "chatgpt", "tokens": {
            "access_token": "ACCESS_PRIVATE_SECRET", "refresh_token": "REFRESH_PRIVATE_SECRET",
            "id_token": "ID_PRIVATE_SECRET", "account_id": "fixture-account",
        }}
        (self.root / "auth.json").write_text(json.dumps(self.auth), encoding="utf-8")

    def snapshot(self):
        return {
            "user_agent": "native-fixture", "environment_policy": "os-paths-only-v1",
            "environment_names": [], "environment_paths_sha256": "environment",
            "config_sha256": "config", "config_layers": [], "skills": [],
            "plugins_enabled": False, "plugin_inventory_sha256": "plugins",
            "instruction_sources": [], "thread_profile": {},
        }

    def test_plain_text_turn_and_matching_identity_only(self):
        client = FakeClient([
            {"method": "turn/completed", "params": {"threadId": "other-thread", "turn": {"id": "turn-1"}}},
            notification("item/completed", {"turnId": "wrong-turn", "item": {"type": "agentMessage", "text": "wrong"}}),
            completed_turn([{"id": "answer", "type": "agentMessage", "phase": "final_answer", "text": "correct"}]),
        ])
        events, _, turn, identity = native.collect_turn(client, "thread-1", "Task only", 1)
        self.assertEqual(client.requests, [("turn/start", {
            "threadId": "thread-1", "input": [{"type": "text", "text": "Task only"}],
        })])
        self.assertEqual(identity, "turn-1")
        self.assertEqual(runner.final_message(events), "correct")
        self.assertEqual(turn["status"], "completed")

    def test_native_commands_reuse_existing_read_evidence(self):
        event = native.normalized_item({
            "id": "cmd", "type": "commandExecution", "command": "rg -n . .agents/skills/bsp/SKILL.md",
            "exitCode": 0, "aggregatedOutput": "Skill text",
        })
        self.assertTrue(runner.skill_activation_evidence([event], "bsp"))
        event["item"]["exit_code"] = 1
        self.assertFalse(runner.skill_activation_evidence([event], "bsp"))

    def test_commentary_is_not_a_final_answer(self):
        self.assertIsNone(native.normalized_item({"type": "agentMessage", "phase": "commentary", "text": "I will do it"}))

    def test_completed_payload_does_not_duplicate_items(self):
        item = {"id": "answer", "type": "agentMessage", "text": "answer"}
        client = FakeClient([
            notification("item/completed", {"turnId": "turn-1", "item": item}),
            completed_turn([item]),
        ])
        events, *_ = native.collect_turn(client, "thread-1", "Task", 1)
        self.assertEqual(sum(event["type"] == "item.completed" for event in events), 1)

    def test_native_usage_is_preserved(self):
        client = FakeClient([
            notification("thread/tokenUsage/updated", {"turnId": "turn-1", "tokenUsage": {
                "total": {"inputTokens": 123, "cachedInputTokens": 12, "outputTokens": 45, "reasoningOutputTokens": 30},
            }}), completed_turn(),
        ])
        events, *_ = native.collect_turn(client, "thread-1", "Task", 1)
        self.assertEqual(runner.usage_from_events(events)["input_tokens"], 123)

    def test_incomplete_native_turn_identity_fails_closed(self):
        client = FakeClient([])
        client.call = lambda *args: {"turn": {}}
        with self.assertRaisesRegex(native.probe.ProbeError, "turn identity"):
            native.collect_turn(client, "thread-1", "Task", 1)

    def test_auth_identity_does_not_depend_on_secret_rotation(self):
        changed = copy.deepcopy(self.auth)
        changed["tokens"]["access_token"] = "rotated-secret"
        self.assertEqual(native.auth_identity(changed), native.auth_identity(self.auth))
        changed["tokens"]["account_id"] = "other-account"
        self.assertNotEqual(native.auth_identity(changed), native.auth_identity(self.auth))

    def test_auth_source_and_private_home_cleanup(self):
        source = (self.root / "auth.json").read_bytes()
        with native.authenticated_home(self.auth) as home:
            self.assertEqual(native.load_auth(home / "auth.json"), self.auth)
            (home / "auth.json").write_text("private refresh")
        self.assertFalse(home.exists())
        self.assertEqual((self.root / "auth.json").read_bytes(), source)

    def test_protection_failure_prevents_credential_write(self):
        with patch.object(native, "private_permissions", side_effect=native.probe.ProbeError("protected")):
            with self.assertRaisesRegex(native.probe.ProbeError, "protected"):
                with native.authenticated_home(self.auth):
                    self.fail("Must not enter context")

    def test_auth_format_is_validated_without_leaking_payload(self):
        (self.root / "auth.json").write_text('{"private":"PRIVATE_SECRET"}')
        with self.assertRaises(native.probe.ProbeError) as caught:
            native.load_auth(self.root / "auth.json")
        self.assertNotIn("PRIVATE_SECRET", str(caught.exception))

    def test_secret_and_private_path_redaction(self):
        text = "ACCESS_PRIVATE_SECRET " + str(self.root) + "/auth.json eyJabc.def.ghi"
        result = native.redact({"text": text}, native.auth_secrets(self.auth), self.root)
        self.assertNotIn("ACCESS_PRIVATE_SECRET", result["text"])
        self.assertNotIn(str(self.root), result["text"])
        self.assertNotIn("eyJabc", result["text"])

    def test_same_process_inventory_is_attached_to_execution(self):
        snapshot = self.snapshot()
        thread = {"thread": {"id": "thread-1"}}
        client = FakeClient([completed_turn([{
            "id": "answer", "type": "agentMessage", "text": "ACCESS_PRIVATE_SECRET answer",
        }])])
        case = runner.EvalCase("fixture", "Task", None, False, False, (), (), ())
        with patch.object(native.probe, "NativeClient", return_value=client), \
                patch.object(native.probe, "initialize_native", return_value={}), \
                patch.object(native.probe, "capture_snapshot", side_effect=[(copy.deepcopy(snapshot), thread), (copy.deepcopy(snapshot), thread)]) as capture:
            execution = native.run_native("unused", case, self.root, self.root, "red", 1,
                                          "model", "medium", 1, "bsp", self.root, "source", native.auth_identity(self.auth))
        self.assertEqual(capture.call_args_list[0].args[0], client)
        self.assertEqual(capture.call_args_list[1].args[0], client)
        self.assertEqual(capture.call_args_list[1].kwargs["thread"], thread)
        self.assertEqual(execution["native_inventory"]["thread_id"], "thread-1")
        self.assertEqual(execution["native_inventory"]["turn_id"], "turn-1")
        self.assertEqual(execution["native_isolation_reasons"], [])
        self.assertEqual(execution["returncode"], 0)
        self.assertNotIn("ACCESS_PRIVATE_SECRET", json.dumps(execution))
        for artifact in self.root.glob("fixture.*"):
            self.assertNotIn("ACCESS_PRIVATE_SECRET", artifact.read_text(encoding="utf-8"))

    def test_native_drift_is_infrastructure_not_quality(self):
        self.assertEqual(runner.infrastructure_reason({
            "native_isolation_reasons": ["drift"], "response": "correct", "returncode": 0,
        }), "native_isolation")

    def test_resume_rejects_changed_transport_identity_and_helpers(self):
        for key in ("transport", "transport_profile", "auth_identity_sha256", "native_helper_sha256", "native_probe_sha256"):
            with self.subTest(key=key), self.assertRaises(runner.EvalError):
                runner.validate_resume_report({"schema_version": 5, key: "before"}, {key: "after"})

    def test_report_gate_accepts_only_bound_equal_environments_and_cleanup(self):
        target = self.root / ".agents" / "skills" / "bsp"
        red = self.snapshot()
        red.update(auth_identity_sha256="identity", native_account_sha256="account")
        green = copy.deepcopy(red)
        green["skills"] = [{
            "name": "bsp", "scope": "repo", "enabled": True, "plugin_id": None,
            "path": str(target / "SKILL.md"), "content_sha256": "skill", "metadata_sha256": "metadata",
        }]
        def receipt(snapshot):
            return {"native_inventory": {
                "profile": native.PROFILE, "launcher_pid": 123,
                "thread_id": "thread", "turn_id": "turn", "before": snapshot, "after": copy.deepcopy(snapshot),
            }}
        report = {"skill_sha256": "skill", "native_restored_red": self.snapshot(), "phases": {
            "red": {"run_matrix": {"case": [receipt(red)]}},
            "green": {"run_matrix": {"case": [receipt(green)]}},
        }}
        self.assertEqual(native.report_inventory_reasons(report, target), [])
        report["native_restored_red"]["config_sha256"] = "drift"
        self.assertTrue(native.report_inventory_reasons(report, target))

    def test_auth_identity_change_blocks_turn_before_client_start(self):
        case = runner.EvalCase("identity", "Task", None, False, False, (), (), ())
        with patch.object(native.probe, "NativeClient") as client:
            execution = native.run_native("unused", case, self.root, self.root, "red", 1,
                                          "model", "medium", 1, "bsp", self.root, "source", "wrong-identity")
        client.assert_not_called()
        self.assertTrue(execution["native_isolation_reasons"])
        self.assertEqual(execution["returncode"], 1)

    def test_report_gate_rejects_missing_turn_and_inventory(self):
        report = {"skill_sha256": "skill", "phases": {"red": {"run_matrix": {
            "case": [{"native_inventory": {"before": self.snapshot(), "after": self.snapshot()}}],
        }}}}
        reasons = native.report_inventory_reasons(report, self.root / "bsp")
        self.assertTrue(any("Missing" in reason for reason in reasons))
        self.assertIn("No actual GREEN runtime inventory", reasons)


if __name__ == "__main__":
    unittest.main()
