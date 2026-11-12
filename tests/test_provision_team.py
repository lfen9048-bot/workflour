import contextlib
import copy
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import uuid

REPO = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("provision_team", REPO / "scripts/provision-team.py")
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


class MemoryClient:
    # Mirrors the accepted subset of native botDefaultsProfileSchema, not a
    # permissive dictionary: memoryEnabled must be a separate native PATCH.
    CREATE_FIELDS = {"name", "title", "description", "soul", "section", "modelSelection",
                     "cwd", "approvalMode", "peers", "approvePeerComms", "computer",
                     "browser", "composio", "helperModel"}

    def __init__(self, roles):
        self.bots = []
        self.calls = []
        self.instances = [
            {"instanceId": r["instance"], "snapshot": {"state": "available"},
             "models": {"options": [{"id": r["modelId"], "variants": [{"id": r["thinking"]}]}]}}
            for r in roles
        ]
        self.fail_memory_once = False
        self.ignore_memory = False
        self.ignore_soul = False
        self.ignore_order = False
        self.fail_post_number = None
        self.post_count = 0
        self.on_fleet = None
        self.create_overrides = {}

    def call(self, method, path, body=None):
        self.calls.append((method, path, copy.deepcopy(body)))
        if method == "GET" and path == "/api/bots?messages=0":
            if self.on_fleet:
                self.on_fleet(self)
            return {"bots": copy.deepcopy(self.bots)}
        if method == "GET" and path == "/api/instances":
            return {"instances": copy.deepcopy(self.instances)}
        if method == "POST" and path == "/api/bots":
            self.post_count += 1
            if self.post_count == self.fail_post_number:
                raise MOD.control.ControlError("simulated network failure")
            if set(body["settings"]) - self.CREATE_FIELDS:
                raise AssertionError("unsupported native create setting")
            if any(b["id"] == body["id"] for b in self.bots):
                raise AssertionError("duplicate creation")
            bot = {**copy.deepcopy(body["settings"]), "id": body["id"],
                   "modelSelection": copy.deepcopy(body["modelSelection"]),
                   "memoryEnabled": True, "busy": False, "tasks": []}
            bot.update(copy.deepcopy(self.create_overrides))
            self.bots.append(bot)
            return {"bot": copy.deepcopy(bot)}
        if method == "PATCH" and path.startswith("/api/bots/"):
            bot = next(b for b in self.bots if b["id"] == path.split("/")[-1])
            if "memoryEnabled" in body:
                if self.fail_memory_once:
                    self.fail_memory_once = False
                    raise MOD.control.ControlError("memory initialization rejected")
                if self.ignore_memory:
                    return {"bot": copy.deepcopy(bot)}
            if self.ignore_soul and "soul" in body:
                body = {k: v for k, v in body.items() if k != "soul"}
            bot.update(copy.deepcopy(body))
            return {"bot": copy.deepcopy(bot)}
        if method == "PUT" and path == "/api/bots/order":
            if not self.ignore_order:
                by_id = {b["id"]: b for b in self.bots}
                if set(by_id) != set(body["botIds"]) or len(body["botIds"]) != len(by_id):
                    raise AssertionError("order dropped or duplicated another Bot")
                self.bots = [by_id[bid] for bid in body["botIds"]]
            return {"ok": True}
        raise AssertionError((method, path))

    @property
    def writes(self):
        return [c for c in self.calls if c[0] != "GET"]


class ProvisionTeamTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "Ubuntu workspace"
        self.root.mkdir()
        self.home = Path(self.temp.name) / "home"
        self.home.mkdir()
        self.team_dir = self.root / "integrations/openmausbot/team-v2"
        self.team_dir.mkdir(parents=True)
        self.roles = json.loads((REPO / "integrations/openmausbot/team-v2/roles.json").read_text())
        self.write_roles()
        for role in self.roles:
            for field in ("soulFile", "skillsFile"):
                p = self.root / role[field]
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text("# " + role["name"] + "\nRead agents/wf-shared/BROWSER.md.\n")
        self.patches = contextlib.ExitStack()
        self.addCleanup(self.patches.close)
        self.patches.enter_context(mock.patch.object(MOD, "ROOT", self.root))
        self.patches.enter_context(mock.patch.object(MOD, "TEAM", self.team_dir))
        self.patches.enter_context(mock.patch.object(MOD.sys, "platform", "linux"))
        self.patches.enter_context(mock.patch.object(Path, "home", return_value=self.home))
        self.patches.enter_context(mock.patch.dict(MOD.os.environ, {}, clear=True))
        self.path = self.home / ".workflour/team-v2/deployment.json"
        self.client = MemoryClient(self.roles)

    def write_roles(self):
        (self.team_dir / "roles.json").write_text(json.dumps(self.roles))

    def prepare(self):
        MOD.provision("prepare", path=self.path)
        return MOD.manifest(self.path)

    def create(self):
        result = MOD.provision("create", path=self.path, client=self.client)
        self.assertTrue(result["ok"], result)
        return MOD.manifest(self.path)

    def test_private_manifest_precedence_and_no_read_side_effects(self):
        self.assertEqual(MOD.manifest_path(), self.path)
        with self.assertRaisesRegex(MOD.control.ControlError, "missing"):
            MOD.manifest()
        self.assertFalse(self.path.exists())
        with mock.patch.dict(MOD.os.environ, {"WORKFLOUR_TEAM_MANIFEST": str(self.home / "env.json")}):
            self.assertEqual(MOD.manifest_path(), self.home / "env.json")
            self.assertEqual(MOD.manifest_path(self.home / "explicit.json"), self.home / "explicit.json")

    def test_prepare_is_offline_stable_private_and_seven_new_ids(self):
        with mock.patch.object(MOD.control, "Client", side_effect=AssertionError("network")):
            first = self.prepare()
            second = self.prepare()
        self.assertEqual(first, second)
        ids = [r["botId"] for r in first["roles"]]
        self.assertEqual(len(set(ids)), 7)
        self.assertTrue(all(str(uuid.UUID(i)) == i for i in ids))
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        self.assertTrue(all(not Path(r["soulFile"]).is_absolute() for r in first["roles"]))

    def test_copied_legacy_mac_manifest_is_not_default_or_accepted_explicitly(self):
        legacy = {"version": 2, "state": "active",
                  "roles": [{**r, "botId": str(uuid.uuid4())} for r in self.roles]}
        (self.team_dir / "deployment.json").write_text(json.dumps(legacy))
        self.assertEqual(MOD.manifest_path(), self.path)
        created = self.prepare()
        self.assertTrue(set(r["botId"] for r in created["roles"]).isdisjoint(r["botId"] for r in legacy["roles"]))
        with self.assertRaisesRegex(MOD.control.ControlError, "Legacy Mac"):
            MOD.manifest(self.team_dir / "deployment.json")

    def test_legacy_original_host_uses_existing_ids_and_current_relative_definitions(self):
        legacy = {"version": 2, "state": "active",
                  "roles": [{**r, "botId": str(uuid.uuid4()),
                             "soulFile": str(MOD.LEGACY_ROOT / r["soulFile"])} for r in self.roles]}
        p = self.team_dir / "deployment.json"
        p.write_text(json.dumps(legacy))
        with mock.patch.object(MOD, "legacy_host", return_value=True):
            self.assertEqual(MOD.manifest_path(), p)
            loaded = MOD.manifest()
        self.assertEqual([r["botId"] for r in loaded["roles"]], [r["botId"] for r in legacy["roles"]])
        self.assertEqual(loaded["roles"][0]["soulFile"], self.roles[0]["soulFile"])
        self.assertTrue(loaded["legacyOwnership"])

    def test_manifest_duplicate_uuid_role_missing_role_and_foreign_platform_rejected(self):
        original = self.prepare()
        variants = []
        v = copy.deepcopy(original); v["roles"][1]["botId"] = v["roles"][0]["botId"]; variants.append(v)
        v = copy.deepcopy(original); v["roles"][0]["botId"] = "not-a-uuid"; variants.append(v)
        v = copy.deepcopy(original); v["roles"][1]["key"] = v["roles"][0]["key"]; variants.append(v)
        v = copy.deepcopy(original); v["roles"].pop(); variants.append(v)
        v = copy.deepcopy(original); v["platform"] = "darwin"; variants.append(v)
        for variant in variants:
            with self.subTest(variant=variants.index(variant)):
                self.path.write_text(json.dumps(variant))
                with self.assertRaises(MOD.control.ControlError):
                    MOD.provision("create", path=self.path, client=self.client)
                self.assertEqual(self.client.writes, [])

    def test_manifest_symlink_is_rejected_without_touching_target(self):
        self.prepare()
        before = self.path.read_bytes()
        link = self.home / "alias.json"
        link.symlink_to(self.path)
        with self.assertRaisesRegex(MOD.control.ControlError, "symlink"):
            MOD.provision("prepare", path=link)
        with mock.patch.dict(MOD.os.environ, {"WORKFLOUR_TEAM_MANIFEST": str(link)}):
            with self.assertRaisesRegex(MOD.control.ControlError, "symlink"):
                MOD.manifest()
        self.assertEqual(self.path.read_bytes(), before)

    def test_role_paths_cannot_escape_repository_or_use_absolute_paths(self):
        for value in ("../outside.md", str(self.root / self.roles[0]["soulFile"])):
            self.roles[0]["soulFile"] = value
            self.write_roles()
            with self.assertRaises(MOD.control.ControlError):
                MOD.provision("create", path=self.path, client=self.client)
        self.assertFalse(self.path.exists())
        self.assertEqual(self.client.writes, [])

    def test_last_missing_catalog_and_invalid_effort_are_preflighted_together(self):
        self.client.instances[-1]["models"]["options"] = []
        self.client.instances[-2]["models"]["options"][0]["variants"] = []
        with self.assertRaises(MOD.control.ControlError) as caught:
            MOD.provision("create", path=self.path, client=self.client)
        self.assertIn("wf-assistant", str(caught.exception))
        self.assertIn("wf-code-helper", str(caught.exception))
        self.assertEqual(self.client.writes, [])
        self.assertFalse(self.path.exists())

    def test_unavailable_and_unconfirmed_catalogs_are_not_treated_as_verified(self):
        for field in ("unavailable", "modelsUnconfirmed", "nestedUnconfirmed"):
            c = MemoryClient(self.roles)
            if field == "unavailable":
                c.instances[-1]["snapshot"]["state"] = "unavailable"
            elif field == "modelsUnconfirmed":
                c.instances[-1]["modelsUnconfirmed"] = True
            else:
                c.instances[-1]["models"]["unconfirmed"] = True
            with self.subTest(field=field), self.assertRaises(MOD.control.ControlError):
                MOD.provision("create", path=self.path, client=c)
            self.assertEqual(c.writes, [])

    def test_missing_last_soul_prevents_all_api_writes(self):
        (self.root / self.roles[-1]["soulFile"]).unlink()
        with self.assertRaises(MOD.control.ControlError):
            MOD.provision("create", path=self.path, client=self.client)
        self.assertEqual(self.client.calls, [])

    def test_create_settings_schema_and_full_are_preserved_memory_is_separate(self):
        self.create()
        creates = [c for c in self.client.calls if c[:2] == ("POST", "/api/bots")]
        self.assertEqual(len(creates), 7)
        self.assertTrue(all(c[2]["settings"]["approvalMode"] == "full" for c in creates))
        self.assertTrue(all("memoryEnabled" not in c[2]["settings"] for c in creates))
        self.assertEqual(len([c for c in self.client.writes if c[0] == "PATCH" and c[2] == {"memoryEnabled": False}]), 7)
        self.assertTrue(all(b["memoryEnabled"] is False for b in self.client.bots))

    def test_idempotent_create_preserves_existing_manual_model_and_permissions(self):
        self.create()
        manual = {"instanceId": "manual-runtime", "model": "chosen", "variant": "low"}
        self.client.bots[0]["modelSelection"] = manual
        self.client.bots[0]["approvalMode"] = "ask"
        self.client.calls.clear()
        result = MOD.provision("create", path=self.path, client=self.client)
        self.assertTrue(result["ok"])
        self.assertEqual(self.client.writes, [])
        self.assertEqual(self.client.bots[0]["modelSelection"], manual)
        self.assertEqual(self.client.bots[0]["approvalMode"], "ask")
        self.assertTrue(result["warnings"])

    def test_new_bot_settings_readback_failure_stays_unconfirmed_on_retry(self):
        self.client.create_overrides = {"approvalMode": "ask", "peers": []}
        for attempt in range(2):
            with self.subTest(attempt=attempt), self.assertRaisesRegex(MOD.control.ControlError, "creation readback"):
                MOD.provision("create", path=self.path, client=self.client)
            self.assertEqual(len(self.client.bots), 1)
            self.assertIn("wf-manager", MOD.manifest(self.path)["pendingCreateReadback"])
        self.assertEqual(self.client.post_count, 1)

    def test_same_uuid_owned_by_other_bot_blocks_all_mutations(self):
        team = self.prepare()
        self.client.bots = [{"id": team["roles"][-1]["botId"], "name": "unrelated", "soul": "not Workflour"}]
        with self.assertRaisesRegex(MOD.control.ControlError, "ownership"):
            MOD.provision("create", path=self.path, client=self.client)
        self.assertEqual(self.client.writes, [])

    def test_swapped_role_ownership_marker_is_rejected(self):
        team = self.create()
        self.client.bots[0]["soul"] = MOD.soul(team["roles"][1], team)
        self.client.calls.clear()
        with self.assertRaisesRegex(MOD.control.ControlError, "ownership"):
            MOD.provision("activate", path=self.path, client=self.client)
        self.assertEqual(self.client.writes, [])

    def test_memory_patch_failure_keeps_ids_and_reentry_finishes_only_journal_fields(self):
        self.client.fail_memory_once = True
        with self.assertRaisesRegex(MOD.control.ControlError, "memory initialization rejected"):
            MOD.provision("create", path=self.path, client=self.client)
        team = MOD.manifest(self.path)
        self.assertEqual(len(self.client.bots), 1)
        self.assertIn(team["roles"][0]["key"], team["pendingInitialization"])
        first_id = self.client.bots[0]["id"]
        manual = {"instanceId": "manual", "model": "chosen"}
        self.client.bots[0]["modelSelection"] = manual
        result = MOD.provision("create", path=self.path, client=self.client)
        self.assertTrue(result["ok"], result)
        self.assertEqual(len(self.client.bots), 7)
        self.assertEqual(self.client.bots[0]["id"], first_id)
        self.assertEqual(self.client.bots[0]["modelSelection"], manual)
        self.assertEqual(MOD.manifest(self.path)["pendingInitialization"], [])

    def test_memory_readback_failure_stays_pending(self):
        self.client.ignore_memory = True
        with self.assertRaisesRegex(MOD.control.ControlError, "not confirmed"):
            MOD.provision("create", path=self.path, client=self.client)
        self.assertEqual(len(self.client.bots), 1)
        self.assertTrue(MOD.manifest(self.path)["pendingInitialization"])
        self.assertFalse(MOD.provision("verify", path=self.path, client=self.client)["ok"])

    def test_pending_initialization_blocks_instructions_and_activation_before_api(self):
        self.client.fail_memory_once = True
        with self.assertRaises(MOD.control.ControlError):
            MOD.provision("create", path=self.path, client=self.client)
        for action in ("instructions", "activate"):
            self.client.calls.clear()
            with self.subTest(action=action), self.assertRaisesRegex(MOD.control.ControlError, "run create"):
                MOD.provision(action, path=self.path, client=self.client)
            self.assertEqual(self.client.calls, [])

    def test_partial_transport_failure_reuses_manifest_ids_on_retry(self):
        self.client.fail_post_number = 3
        with self.assertRaisesRegex(MOD.control.ControlError, "network failure"):
            MOD.provision("create", path=self.path, client=self.client)
        before = MOD.manifest(self.path)
        self.assertEqual(len(self.client.bots), 2)
        result = MOD.provision("create", path=self.path, client=self.client)
        self.assertTrue(result["ok"], result)
        self.assertEqual([r["botId"] for r in before["roles"]],
                         [r["botId"] for r in MOD.manifest(self.path)["roles"]])
        self.assertEqual(len(self.client.bots), 7)

    def test_busy_late_role_blocks_all_instruction_and_activate_writes(self):
        self.create()
        self.client.bots[-1]["tasks"] = [{"threadId": "running", "busy": True}]
        for action in ("instructions", "activate"):
            self.client.calls.clear()
            with self.subTest(action=action), self.assertRaisesRegex(MOD.control.ControlError, "busy"):
                MOD.provision(action, path=self.path, client=self.client)
            self.assertEqual(self.client.writes, [])

    def test_selected_idle_instructions_preserve_model_and_other_busy_role(self):
        team = self.create()
        self.client.bots[-1]["busy"] = True
        manual = {"instanceId": "another", "model": "choice"}
        self.client.bots[0]["modelSelection"] = manual
        (self.root / self.roles[0]["soulFile"]).write_text("# Changed manager duties\n")
        self.client.calls.clear()
        result = MOD.provision("instructions", path=self.path, role_keys=["wf-manager"], client=self.client)
        self.assertTrue(result["ok"], result)
        self.assertEqual(len(self.client.writes), 1)
        self.assertEqual(self.client.writes[0][1], "/api/bots/" + team["roles"][0]["botId"])
        self.assertEqual(set(self.client.writes[0][2]), {"soul"})
        self.assertEqual(self.client.bots[0]["modelSelection"], manual)

    def test_activate_retains_every_other_bot_and_their_relative_order(self):
        team = self.create()
        others = [{"id": str(uuid.uuid4()), "name": n} for n in ("System", "Other project", "Archive")]
        self.client.bots = [others[0], self.client.bots[0], others[1], *self.client.bots[1:], others[2]]
        result = MOD.provision("activate", path=self.path, client=self.client)
        self.assertTrue(result["ok"], result)
        self.assertEqual([b["id"] for b in self.client.bots],
                         [r["botId"] for r in team["roles"]] + [b["id"] for b in others])
        self.assertEqual(MOD.manifest(self.path)["state"], "active")

    def test_activate_readback_failure_does_not_mark_staging_team_active(self):
        self.create()
        self.client.ignore_soul = True
        (self.root / self.roles[-1]["soulFile"]).write_text("# new duties\n")
        result = MOD.provision("activate", path=self.path, client=self.client)
        self.assertFalse(result["ok"])
        self.assertEqual(MOD.manifest(self.path)["state"], "staging")
        self.assertIn("instructions readback differs", " ".join(result["errors"]))

    def test_verify_missing_model_or_bot_fails_cli_without_mutation(self):
        self.create()
        self.client.bots[-1].pop("modelSelection")
        self.client.bots.pop(0)
        self.client.calls.clear()
        with mock.patch.object(MOD.control, "Client", return_value=self.client), contextlib.redirect_stdout(io.StringIO()):
            status = MOD.main(["verify", "--manifest", str(self.path)])
        self.assertEqual(status, 1)
        self.assertEqual(self.client.writes, [])

    def test_soul_uses_host_paths_vault_override_and_historical_evidence_warning(self):
        p = self.root / self.roles[0]["soulFile"]
        p.write_text("Read " + str(MOD.LEGACY_ROOT) + "/agents/wf-shared/BROWSER.md and " + MOD.LEGACY_VAULT)
        team = self.prepare()
        with mock.patch.dict(MOD.os.environ, {"WORKFLOUR_OBSIDIAN_VAULT": str(self.home / "my vault")}):
            text = MOD.soul(team["roles"][0], team)
        self.assertNotIn(str(MOD.LEGACY_ROOT), text)
        self.assertNotIn(MOD.LEGACY_VAULT, text)
        self.assertIn(str(self.root), text)
        self.assertIn(str(self.home / "my vault"), text)
        self.assertIn("绝不是业务项目 cwd", text)
        self.assertIn("不代表本机已安装", text)
        self.assertIn(str(self.home / "Documents/Obsidian/Workflour"),
                      MOD.soul(team["roles"][0], team))


if __name__ == "__main__":
    unittest.main()
