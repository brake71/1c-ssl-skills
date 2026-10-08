import copy
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ci import probe_eval_isolation as probe


class IsolationProbeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.workdir = self.root / "consumer"
        self.workdir.mkdir()
        self.skill = self.root / "source" / "bsp"
        self.skill.mkdir(parents=True)
        (self.skill / "SKILL.md").write_text(
            "---\nname: bsp\ndescription: Fixture BSP\n---\nBody\n", encoding="utf-8",
        )
        self.home = self.root / "home"
        self.home.mkdir()
        self.target = self.workdir / ".agents" / "skills" / "bsp"
        self.source_hash = probe.evals.skill_sha256(self.skill)

    def record(self, name="common", scope="system", path="/common/SKILL.md"):
        return {
            "name": name, "scope": scope, "path": path, "enabled": True,
            "plugin_id": None, "metadata_sha256": "metadata", "content_sha256": "bytes",
        }

    def snapshot(self):
        return {
            "user_agent": "native/fixture", "config_sha256": "config",
            "environment_policy": "os-paths-only-v1",
            "environment_names": ["PATH"], "environment_paths_sha256": "paths",
            "config_layers": [], "skills": [self.record()],
            "plugins_enabled": False, "plugin_inventory_sha256": "plugins",
            "instruction_sources": [], "thread_profile": {"model": "model"},
        }

    def snapshots(self):
        red = self.snapshot()
        green = copy.deepcopy(red)
        staged = self.record("bsp", "repo", str(self.target / "SKILL.md"))
        staged["content_sha256"] = self.source_hash
        green["skills"].append(staged)
        # Native records are sorted by path; comparator excludes staged BSP.
        green["skills"].sort(key=lambda item: (item["path"], item["name"]))
        return red, green, copy.deepcopy(red)

    def reasons(self, snapshots):
        return probe.compare_snapshots(
            *snapshots, self.target, "bsp", self.source_hash,
        )

    def test_only_staged_bsp_is_a_valid_delta(self):
        self.assertEqual(self.reasons(self.snapshots()), [])

    def test_staged_bsp_must_match_bytes_and_be_enabled_repo_skill(self):
        for field, value in (("enabled", False), ("scope", "user"),
                             ("content_sha256", "changed"), ("name", "other"),
                             ("plugin_id", "plugin-owner")):
            with self.subTest(field=field):
                snapshots = self.snapshots()
                staged = next(item for item in snapshots[1]["skills"] if item["name"] == "bsp")
                staged[field] = value
                self.assertIn("GREEN must discover exactly the enabled staged BSP bytes", self.reasons(snapshots))

    def test_missing_staged_skill_fails(self):
        red, _, restored = self.snapshots()
        self.assertTrue(self.reasons((red, copy.deepcopy(red), restored)))

    def test_extra_bsp_from_another_root_fails(self):
        snapshots = self.snapshots()
        snapshots[1]["skills"].append(self.record("bsp", "user", "/global/bsp/SKILL.md"))
        self.assertIn("GREEN changes skills other than staged BSP", self.reasons(snapshots))

    def test_disabled_bsp_still_contaminates_red(self):
        snapshots = self.snapshots()
        bsp = self.record("BSP", "user", "/global/bsp/SKILL.md")
        bsp["enabled"] = False
        snapshots[0]["skills"].append(bsp)
        self.assertIn("RED discovers bsp", self.reasons(snapshots))

    def test_other_project_skill_contaminates_red(self):
        snapshots = self.snapshots()
        snapshots[0]["skills"].append(self.record("other", "repo"))
        self.assertIn("RED discovers other project skills", self.reasons(snapshots))

    def test_common_skill_content_and_metadata_drift_fail(self):
        for field in ("content_sha256", "metadata_sha256", "enabled"):
            with self.subTest(field=field):
                snapshots = self.snapshots()
                common = next(item for item in snapshots[1]["skills"] if item["name"] == "common")
                common[field] = "changed"
                self.assertIn("GREEN changes skills other than staged BSP", self.reasons(snapshots))

    def test_environment_and_config_drift_fail(self):
        for field in ("user_agent", "environment_policy", "environment_names", "environment_paths_sha256",
                      "config_sha256", "config_layers", "plugins_enabled",
                      "plugin_inventory_sha256", "instruction_sources", "thread_profile"):
            with self.subTest(field=field):
                snapshots = self.snapshots()
                snapshots[1][field] = "changed"
                self.assertIn(f"Native environment differs: {field}", self.reasons(snapshots))

    def test_restored_catalog_must_equal_initial_red(self):
        snapshots = self.snapshots()
        snapshots[2]["skills"].clear()
        self.assertIn("Catalog changes after staged BSP cleanup", self.reasons(snapshots))

    def test_audit_stages_and_cleans_up(self):
        calls = []
        snapshots = self.snapshots()
        def snapshot(*args):
            calls.append(self.target.exists())
            return snapshots[len(calls) - 1]
        result = probe.run_audit(self.skill, self.workdir, self.home, [], 1, snapshot)
        self.assertEqual(calls, [False, True, False])
        self.assertTrue(result["catalog_gate"]["passed"])
        self.assertFalse(self.target.exists())

    def test_audit_cleans_up_when_green_inventory_fails(self):
        calls = []
        def snapshot(*args):
            calls.append(True)
            if len(calls) == 2:
                raise probe.ProbeError("No native inventory")
            return self.snapshot()
        with self.assertRaisesRegex(probe.ProbeError, "No native inventory"):
            probe.run_audit(self.skill, self.workdir, self.home, [], 1, snapshot)
        self.assertFalse(self.target.exists())

    def test_contaminated_red_fails_before_staging(self):
        snapshot = self.snapshot()
        snapshot["skills"].append(self.record("bsp", "user"))
        with self.assertRaisesRegex(probe.ProbeError, "RED already discovers"):
            probe.run_audit(self.skill, self.workdir, self.home, [], 1, lambda *args: snapshot)
        self.assertFalse(self.target.exists())

    def test_existing_target_is_not_overwritten(self):
        self.target.mkdir(parents=True)
        sentinel = self.target / "user.txt"
        sentinel.write_text("untouched")
        with self.assertRaisesRegex(probe.ProbeError, "Refusing to overwrite"):
            probe.run_audit(self.skill, self.workdir, self.home, [], 1)
        self.assertEqual(sentinel.read_text(), "untouched")

    def test_linked_staging_parents_are_rejected(self):
        with patch.object(probe, "is_linked", side_effect=lambda path: path == self.target.parent):
            with self.assertRaisesRegex(probe.ProbeError, "linked"):
                probe.run_audit(self.skill, self.workdir, self.home, [], 1)

    def test_windows_reparse_points_are_rejected_without_is_junction_api(self):
        class Info:
            st_file_attributes = 0x400
        class OldPath:
            def is_symlink(self):
                return False
            def lstat(self):
                return Info()
        with patch.object(probe.os, "name", "nt"):
            self.assertTrue(probe.is_linked(OldPath()))
            Info.st_file_attributes = 0
            self.assertFalse(probe.is_linked(OldPath()))

    def test_linked_report_path_is_rejected_before_native_process(self):
        output = self.root / "report-link.json"
        args = ["probe", "--dir", str(self.workdir), "--output", str(output)]
        with patch.object(sys, "argv", args), patch.object(probe, "is_linked", return_value=True), \
                patch.object(probe, "native_snapshot") as snapshot, patch("sys.stdout", new=io.StringIO()):
            with self.assertRaises(SystemExit) as caught:
                probe.main()
        self.assertEqual(caught.exception.code, 2)
        snapshot.assert_not_called()
        self.assertFalse(output.exists())

    def test_inventory_uses_disposable_home_marker_without_raw_dependencies(self):
        path = self.home / "skills" / "common" / "SKILL.md"
        path.parent.mkdir(parents=True)
        path.write_text("fixture")
        raw = self.record(path=str(path))
        raw["dependencies"] = {"url": "https://user:secret@example.test"}
        result = probe.skill_record(raw, self.home)
        self.assertEqual(result["path"], "$AUDIT_CODEX_HOME/skills/common/SKILL.md")
        self.assertNotIn("secret", json.dumps(result))
        self.assertNotIn(str(self.home), json.dumps(result))

    def test_nested_metadata_paths_are_stable_across_disposable_homes(self):
        other_home = self.root / "another-home"
        records = []
        for home in (self.home, other_home):
            path = home / "skills" / "common" / "SKILL.md"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("same bytes")
            raw = self.record(path=str(path))
            raw["interface"] = {"iconSmall": str(home / "icons" / "small.png")}
            records.append(probe.skill_record(raw, home))
        self.assertEqual(records[0], records[1])

    def test_metadata_path_prefix_does_not_mask_unrelated_directory(self):
        path = self.home / "common" / "SKILL.md"
        path.parent.mkdir()
        path.write_text("same bytes")
        raw = self.record(path=str(path))
        raw["interface"] = {"iconSmall": str(self.home) + "-unrelated/icon.png"}
        first = probe.skill_record(raw, self.home)
        raw["interface"]["iconSmall"] = "$AUDIT_CODEX_HOME-unrelated/icon.png"
        self.assertNotEqual(first["metadata_sha256"], probe.skill_record(raw, self.home)["metadata_sha256"])

    def test_invalid_skill_metadata_fails_closed(self):
        for raw in (None, "not-a-record", {}, {"name": "common", "enabled": "true"}):
            with self.subTest(raw=raw), self.assertRaises(probe.ProbeError):
                probe.skill_record(raw, self.home)

    def test_environment_only_forwards_os_paths_not_credentials_or_integrations(self):
        environment = probe.audit_environment(self.home, {
            "PATH": "/tools", "USERPROFILE": "/user", "TEMP": "/temp",
            "OPENAI_API_KEY": "private-key", "CODEX_HOME": "/global/codex",
            "CODEX_CONFIG": "private-config", "SOME_UNKNOWN_SECRET": "private-token",
            "HERDR_AUTH_TOKEN": "private-token", "HTTP_PROXY": "https://user:private-token@proxy",
        })
        self.assertEqual(environment["PATH"], "/tools")
        self.assertEqual(environment["CODEX_HOME"], str(self.home))
        self.assertNotIn("private", json.dumps(environment))
        self.assertEqual(set(environment), {
            "PATH", "USERPROFILE", "TEMP", "CODEX_HOME", "PYTHONIOENCODING", "PYTHONUTF8",
        })

    def test_commands_do_not_start_a_model_turn_and_pin_restrictions(self):
        command = probe.audit_command("cdx", self.workdir, "exact-model", "medium")
        self.assertEqual(command[:3], ["cdx", "app-server", "--stdio"])
        self.assertNotIn("exec", command)
        self.assertNotIn("--ignore-user-config", command)
        self.assertIn('model="exact-model"', command)
        self.assertIn('model_reasoning_effort="medium"', command)
        for feature in probe.DISABLED_FEATURES:
            self.assertIn(f"features.{feature}=false", command)

    def test_development_repository_and_output_in_consumer_are_rejected(self):
        with self.assertRaisesRegex(probe.ProbeError, "outside the development"):
            probe.validate_workdir(probe.evals.REPO_ROOT / "src", self.root / "audit.json")
        with self.assertRaisesRegex(probe.ProbeError, "outside the consumer"):
            probe.validate_workdir(self.workdir, self.workdir / "audit.json")

    def test_external_git_root_is_accepted_but_not_subdirectory(self):
        subprocess.run(["git", "init", "-q", str(self.workdir)], check=True)
        probe.validate_workdir(self.workdir, self.root / "audit.json")
        child = self.workdir / "child"
        child.mkdir()
        with self.assertRaisesRegex(probe.ProbeError, "not a subdirectory"):
            probe.validate_workdir(child, self.root / "audit.json")

    def native_responses(self):
        raw_skill = self.record(path=str(self.skill / "SKILL.md"))
        return {
            "initialize": {"codexHome": str(self.home), "userAgent": "fixture"},
            "config/read": {
                "config": {"features": {feature: False for feature in probe.DISABLED_FEATURES},
                           "mcp_servers": {}, "private_setting": "private-token"},
                "layers": [{"name": {"type": "sessionFlags"}, "config": {"private_setting": "private-token"}}],
            },
            "skills/list": {"data": [{"cwd": str(self.workdir), "errors": [], "skills": [raw_skill]}]},
            "plugin/list": {"marketplaces": [], "marketplaceLoadErrors": []},
            "thread/start": {
                "cwd": str(self.workdir), "instructionSources": [], "disabledPluginIds": [],
                "approvalPolicy": "never", "sandbox": {"type": "readOnly"},
            },
        }

    def mock_native_snapshot(self, responses):
        with patch.object(probe, "NativeClient") as constructor:
            client = constructor.return_value
            client.call.side_effect = lambda method, params: responses[method]
            with patch.dict(os.environ, {"OPENAI_API_KEY": "private-token"}):
                result = probe.native_snapshot([], self.workdir, self.home, 1)
            self.assertNotIn("OPENAI_API_KEY", constructor.call_args.args[2])
            self.assertEqual([call.args[0] for call in client.call.call_args_list], [
                "initialize", "config/read", "skills/list", "plugin/list", "thread/start",
            ])
            client.close.assert_called_once()
            return result

    def test_native_snapshot_never_starts_turn_or_persists_config_secrets(self):
        result = self.mock_native_snapshot(self.native_responses())
        self.assertNotIn("private-token", json.dumps(result))

    def test_native_inventory_errors_and_wrong_cwd_fail_closed(self):
        for field, value in (("errors", [{"message": "failure"}]), ("cwd", str(self.root)),
                             ("skills", None)):
            with self.subTest(field=field):
                responses = self.native_responses()
                responses["skills/list"]["data"][0][field] = value
                with self.assertRaises(probe.ProbeError):
                    self.mock_native_snapshot(responses)

    def test_native_profile_and_plugin_inventory_must_be_complete(self):
        for method, field, value in (
            ("config/read", "layers", None),
            ("plugin/list", "marketplaceLoadErrors", [{"error": "failed"}]),
            ("plugin/list", "marketplaces", [{"name": "unexpected-plugin"}]),
            ("thread/start", "instructionSources", ["/global/AGENTS.md"]),
            ("thread/start", "disabledPluginIds", None),
            ("thread/start", "sandbox", None),
        ):
            with self.subTest(method=method, field=field):
                responses = self.native_responses()
                responses[method][field] = value
                with self.assertRaises(probe.ProbeError):
                    self.mock_native_snapshot(responses)

    def test_enabled_plugins_or_mcp_servers_are_rejected(self):
        for change in ("plugins", "mcp"):
            with self.subTest(change=change):
                responses = self.native_responses()
                config = responses["config/read"]["config"]
                if change == "plugins":
                    config["features"]["plugins"] = True
                else:
                    config["mcp_servers"] = {"extra": {}}
                with self.assertRaises(probe.ProbeError):
                    self.mock_native_snapshot(responses)

    def test_rpc_rejects_errors_without_persisting_raw_secret(self):
        program = (
            "import sys,json\n"
            "for line in sys.stdin:\n"
            " request=json.loads(line)\n"
            " print(json.dumps({'id':request['id'],'error':{'message':'private-token'}}),flush=True)\n"
        )
        client = probe.NativeClient([sys.executable, "-u", "-c", program], self.workdir, dict(os.environ), 2)
        try:
            with self.assertRaisesRegex(probe.ProbeError, "Native RPC rejected inventory") as caught:
                client.call("inventory", {})
            self.assertNotIn("private-token", str(caught.exception))
        finally:
            client.close()

    def test_rpc_preserves_early_notifications_and_matches_response_id(self):
        program = (
            "import sys,json\n"
            "for line in sys.stdin:\n"
            " request=json.loads(line)\n"
            " print(json.dumps({'method':'notification','params':{}}),flush=True)\n"
            " print(json.dumps({'id':request['id'],'result':{'ok':True}}),flush=True)\n"
        )
        client = probe.NativeClient([sys.executable, "-u", "-c", program], self.workdir, dict(os.environ), 2)
        try:
            self.assertEqual(client.call("inventory", {}), {"ok": True})
            self.assertEqual(client.next_notification(1), {"method": "notification", "params": {}})
        finally:
            client.close()


if __name__ == "__main__":
    unittest.main()
