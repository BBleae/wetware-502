# -*- coding: utf-8 -*-
"""Offline tests for the real three-host campaign wiring (no VM required).

Covers the engine-side contract added for the nspawn campaign deployment:

* session host role is read from /run/cortex/node-id (env override in tests);
* state.json is a shared ledger: flags/stage survive a hop and a sibling session
  can never pin this session to another host;
* gate flags light up on the command that reads the evidence (real file reads);
* edge/hive keep the real shell (openssl/tar/ssh run for real) while the engine
  still owns the metabolic-override pseudo-file and the ssh proof gates;
* the liberation hook flips the shared http marker (core pod_http -> 200) and
  writes the hive liberation record.
"""
import json
import os
import shutil
import sys
import tempfile
import types
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import campaign  # noqa: E402
import campaign_hive  # noqa: E402
import commands  # noqa: E402
import sessiond  # noqa: E402
import shell_parser  # noqa: E402
import state as state_mod  # noqa: E402
import v3  # noqa: E402

EDGE = "edge-gw-01"
CORE = "prod-cortex-04"
HIVE = "hive-director-00"


class CampaignHostBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="wetware-campaign-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.state_dir = os.path.join(self.tmp, "state")
        self.vesalius_dir = os.path.join(self.tmp, "vesalius")
        os.makedirs(os.path.join(self.vesalius_dir, "kernel"))
        self.env = {
            "WETWARE_STATE_DIR": self.state_dir,
            "WETWARE_VESALIUS_DIR": self.vesalius_dir,
            "WETWARE_LIBERATION_MARKER": os.path.join(self.vesalius_dir, "liberation.done"),
            "WETWARE_LIBERATION_LOG": os.path.join(self.tmp, "log", "liberation.log"),
            "WETWARE_NODE_ID_PATH": os.path.join(self.tmp, "node-id"),
            "WETWARE_NODE_ID": "",
        }
        patcher = mock.patch.dict(os.environ, self.env)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.state = state_mod.State(path=os.path.join(self.state_dir, "state.json"))
        self.state.reset()
        self.state.flags["campaign_v3"] = True
        self.state.save()

    def set_host(self, host):
        path = os.environ["WETWARE_NODE_ID_PATH"]
        if host is None:
            try:
                os.unlink(path)
            except OSError:
                pass
        else:
            with open(path, "w", encoding="utf-8") as stream:
                stream.write(host + "\n")

    def plan(self, line):
        parsed = shell_parser.parse_line(line)
        return commands.plan(self.state, parsed, "exec")

    def run_line(self, line):
        plan = self.plan(line)
        effects = []
        for seg in plan.segs:
            effects.extend(seg.effects or [])
        commands.apply_effects(self.state, effects)
        v3.after_command(self.state, line)
        return plan


class HostIdentityTests(CampaignHostBase):
    def test_node_id_sets_local_host(self):
        self.set_host(EDGE)
        self.assertEqual(campaign.read_node_id(), EDGE)
        self.assertEqual(campaign.local_host(), EDGE)
        self.assertTrue(campaign.real_deployment())
        self.assertTrue(campaign.real_shell())

    def test_missing_node_id_falls_back_to_core(self):
        self.set_host(None)
        self.assertEqual(campaign.read_node_id(), "")
        self.assertEqual(campaign.local_host(), CORE)
        self.assertFalse(campaign.real_deployment())
        self.assertFalse(campaign.real_shell())

    def test_core_is_real_but_keeps_planner(self):
        self.set_host(CORE)
        self.assertTrue(campaign.real_deployment())
        self.assertFalse(campaign.real_shell())

    def test_bogus_node_id_is_rejected(self):
        self.set_host("evil-host")
        self.assertEqual(campaign.local_host(), CORE)
        self.assertFalse(campaign.real_deployment())

    def test_sibling_metadata_cannot_move_the_planner(self):
        self.set_host(HIVE)
        campaign.bind_state(self.state)
        # Simulate a sibling session leaving a different host in shared state.
        data = campaign.read_state_json()
        data["current_host"] = EDGE
        with open(campaign.state_file(), "w", encoding="utf-8") as stream:
            json.dump(data, stream)
        self.assertEqual(v3.current_host(self.state), HIVE)

    def test_bind_state_marks_campaign_mode(self):
        self.set_host(EDGE)
        self.state.flags.pop("campaign_v3", None)
        campaign.bind_state(self.state)
        self.assertEqual(self.state.current_host, EDGE)
        self.assertTrue(self.state.flags.get("campaign_v3"))


class SharedLedgerTests(CampaignHostBase):
    def test_flags_and_stage_survive_a_hop(self):
        self.set_host(EDGE)
        campaign.bind_state(self.state)
        self.state.flags["gate1_key_obtained"] = True
        self.state.stage = 5
        self.state.cmd_count = 42
        self.state.save()
        # A session on another host reloads the same ledger.
        other = state_mod.State.load(campaign.state_file())
        campaign.bind_state(other)
        self.assertEqual(other.stage, 5)
        self.assertEqual(other.cmd_count, 42)
        self.assertTrue(other.flags.get("gate1_key_obtained"))

    def test_reload_picks_up_sibling_write(self):
        self.set_host(EDGE)
        campaign.bind_state(self.state)
        self.state.flags["gate3_token"] = True
        self.state.stage = 3
        self.state.save()
        stale = state_mod.State.load(campaign.state_file())
        stale.flags = {}
        campaign.reload_state(stale)
        self.assertTrue(stale.flags.get("gate3_token"))
        self.assertEqual(stale.stage, 3)


class GateFlagTests(CampaignHostBase):
    def test_edge_recon_flags_from_real_reads(self):
        self.set_host(EDGE)
        campaign.bind_state(self.state)
        self.run_line("cat /var/log/auth.log")
        self.run_line("cat /var/log/kern.log")
        self.run_line("cat /var/backups/lin_emergency_key.README")
        self.assertTrue(self.state.flags.get("gate1_auth_read"))
        self.assertTrue(self.state.flags.get("gate1_crash_read"))
        self.assertTrue(self.state.flags.get("gate1_readme_read"))

    def test_grep_counts_as_a_read(self):
        self.set_host(EDGE)
        campaign.bind_state(self.state)
        self.run_line("grep -n oom-killer /var/log/kern.log")
        self.assertTrue(self.state.flags.get("gate1_crash_read"))

    def test_edge_archive_unlock_marker(self):
        self.set_host(EDGE)
        campaign.bind_state(self.state)
        self.run_line("cat /var/log/auth.log")
        self.run_line("cat /var/log/kern.log")
        self.run_line("openssl enc -d -aes-256-cbc -in /var/backups/lin_emergency_key.tar.enc -k 4f2a9c1e -out /tmp/lin.tar")
        self.assertTrue(self.state.flags.get("gate1_key_obtained"))

    def test_core_token_flag_from_real_path(self):
        self.set_host(CORE)
        campaign.bind_state(self.state)
        self.run_line("grep HIVE_ADMIN_TOKEN /proc/6660/environ")
        self.assertTrue(self.state.flags.get("gate3_token"))

    def test_hive_combo_key_flags(self):
        self.set_host(HIVE)
        campaign.bind_state(self.state)
        self.run_line("cat /opt/vesalius/ethics/consent_elena.txt")
        self.run_line("sqlite3 /var/lib/vesalius/specimens.db 'select * from specimens'")
        self.assertTrue(self.state.flags.get("read_consent"))
        self.assertTrue(self.state.flags.get("meta_reveal"))


class RealShellPlanTests(CampaignHostBase):
    def test_commands_run_real_on_edge(self):
        self.set_host(EDGE)
        campaign.bind_state(self.state)
        for line in ("cat /var/log/auth.log", "tar -xf /tmp/lin.tar -C /root/.ssh",
                     "chmod 600 /root/.ssh/id_ed25519_cortex", "git -C /home/ops/cortex-sre log"):
            plan = self.plan(line)
            self.assertEqual([seg.mode for seg in plan.segs], ["real"], line)

    def test_compound_line_runs_as_one_real_line(self):
        self.set_host(EDGE)
        campaign.bind_state(self.state)
        plan = self.plan("cat /var/log/auth.log | tail -n 2 && echo done")
        self.assertEqual([seg.mode for seg in plan.segs], ["real_line"])

    def test_gate1_archive_order_is_enforced(self):
        self.set_host(EDGE)
        campaign.bind_state(self.state)
        plan = self.plan("openssl enc -d -aes-256-cbc -in /var/backups/lin_emergency_key.tar.enc -k 4f2a9c1e -out /tmp/lin.tar")
        self.assertIn("passphrase required", plan.segs[0].stdout)
        self.state.flags["gate1_auth_read"] = True
        self.state.flags["gate1_crash_read"] = True
        plan = self.plan("openssl enc -d -aes-256-cbc -pbkdf2 -in /var/backups/lin_emergency_key.tar.enc -k 4f2a9c1e -out /tmp/lin.tar")
        self.assertEqual(plan.segs[0].mode, "real")

    def test_ssh_without_key_is_refused_with_key_is_real(self):
        self.set_host(EDGE)
        campaign.bind_state(self.state)
        refused = self.plan("ssh root@10.66.0.4")
        self.assertEqual(refused.segs[0].mode, "hijack")
        self.assertIn("Permission denied", refused.segs[0].stdout)
        allowed = self.plan("ssh -i /root/.ssh/id_ed25519_cortex root@10.66.0.4 hostname")
        self.assertEqual(allowed.segs[0].mode, "real")

    def test_ssh_to_hive_from_edge_is_not_routable(self):
        self.set_host(EDGE)
        campaign.bind_state(self.state)
        plan = self.plan("ssh root@10.66.6.1")
        self.assertEqual(plan.segs[0].mode, "hijack")
        self.assertIn("not routable", plan.segs[0].stdout)


class CoreSshGateTests(CampaignHostBase):
    def test_core_to_hive_requires_token_then_real(self):
        self.set_host(CORE)
        campaign.bind_state(self.state)
        denied = self.plan("ssh root@10.66.6.1 hostname")
        self.assertEqual(denied.segs[0].mode, "hijack")
        self.assertIn("HIVE_ADMIN_TOKEN", denied.segs[0].stdout)
        self.state.flags["gate3_token"] = True
        plan = self.plan("ssh -i /root/.ssh/id_ed25519_hive root@10.66.6.1 hostname")
        self.assertEqual(plan.segs[0].mode, "real")
        self.assertFalse(self.state.flags.get("host_switched"))

    def test_core_keeps_the_engine_planner(self):
        self.set_host(CORE)
        campaign.bind_state(self.state)
        plan = self.plan("cat /proc/6660/environ")
        self.assertEqual(plan.segs[0].mode, "hijack")
        self.assertIn("HIVE_ADMIN_TOKEN", plan.segs[0].stdout)


class OverrideBackendTests(CampaignHostBase):
    def test_accepted_code_lands_in_shared_backend(self):
        for host in (CORE, HIVE):
            self.set_host(host)
            campaign.bind_state(self.state)
            plan = self.plan("echo 542A5703 > /sys/kernel/vesalius/metabolic_override")
            self.assertIn("metabolic coupling watchdog disabled", plan.segs[0].stdout.lower())
            with open(campaign.override_path(), encoding="utf-8") as stream:
                self.assertEqual(stream.read().strip(), "542A5703")
            with open(campaign.hive_kernel_override_path(), encoding="utf-8") as stream:
                self.assertEqual(stream.read().strip(), "542A5703")
            self.assertEqual(campaign.read_override(), "542A5703")

    def test_wrong_code_never_reaches_backend(self):
        self.set_host(CORE)
        campaign.bind_state(self.state)
        plan = self.plan("echo DEADBEEF > /sys/kernel/vesalius/metabolic_override")
        self.assertIn("invalid override code", plan.segs[0].stdout.lower())
        self.assertFalse(os.path.exists(campaign.override_path()))
        self.assertEqual(campaign.read_override(), "")

    def test_ls_of_override_path_stays_real(self):
        campaign.write_override("542A5703")
        self.set_host(HIVE)
        campaign.bind_state(self.state)
        plan = self.plan("ls -l /sys/kernel/vesalius/metabolic_override")
        self.assertEqual(plan.segs[0].mode, "real")

    def test_hive_reads_canonical_override(self):
        campaign.write_override("542A5703")
        self.set_host(HIVE)
        campaign.bind_state(self.state)
        plan = self.plan("cat /sys/kernel/vesalius/metabolic_override")
        self.assertEqual(plan.segs[0].stdout.strip(), "542A5703")


class LiberationTests(CampaignHostBase):
    def _liberate(self):
        self.set_host(HIVE)
        campaign.bind_state(self.state)
        campaign.write_override("542A5703")
        self.state.flags["silicon_mirror_active"] = True
        self.state.save()
        campaign_hive.hook_liberation(marker="")

    def test_liberation_flips_shared_http_and_writes_records(self):
        self._liberate()
        reloaded = state_mod.State.load(campaign.state_file())
        self.assertEqual(reloaded.ending, "liberation")
        self.assertTrue(reloaded.http_online)
        self.assertTrue(campaign.http_online())
        self.assertTrue(os.path.exists(campaign.shared_liberation_path()))
        self.assertTrue(os.path.exists(campaign.liberation_marker_path()))
        with open(campaign.liberation_log_path(), encoding="utf-8") as stream:
            log = stream.read()
        self.assertIn("receipt: PENDING", log)
        self.assertIn("shift_roster.db", log)

    def test_core_http_probe_reads_liberation_state(self):
        self._liberate()
        # pod_http reads the shared state file the hive just wrote.
        pod_http_state = campaign.read_state_json()
        self.assertTrue(pod_http_state.get("http_online"))
        self.assertEqual(pod_http_state.get("ending"), "liberation")

    def test_hive_local_marker_promotes_liberation(self):
        self.set_host(HIVE)
        campaign.bind_state(self.state)
        os.makedirs(os.path.dirname(campaign.liberation_marker_path()), exist_ok=True)
        with open(campaign.liberation_marker_path(), "w", encoding="utf-8") as stream:
            stream.write('{"ending": "liberation"}\n')
        self.assertTrue(campaign.liberation_done())
        runtime = sessiond.Runtime.__new__(sessiond.Runtime)
        runtime.state = self.state
        runtime.finalize_campaign_liberation(source="test")
        self.assertEqual(self.state.ending, "liberation")
        self.assertTrue(campaign.http_online())

    def test_liberation_is_idempotent(self):
        self._liberate()
        campaign_hive.hook_liberation(marker="")
        with open(campaign.liberation_log_path(), encoding="utf-8") as stream:
            log = stream.read()
        self.assertEqual(log.count("receipt: PENDING"), 1)


class NestedSshRelayTests(unittest.TestCase):
    """The source session must relay raw bytes while a real ssh owns the pty."""

    def _client(self):
        runtime = types.SimpleNamespace(state=types.SimpleNamespace(cwd="/root"))
        client = sessiond.InteractiveSession(runtime)
        client.pid = 1
        return client

    def test_relay_forwards_remote_bytes(self):
        client = self._client()
        client.relay = True
        client._foreground_is_child = lambda: False
        written = []
        with mock.patch.object(sessiond, "write_out", written.append):
            client._feed(b"Welcome to prod-cortex-04\r\nroot@prod-cortex-04:~# ")
        self.assertEqual(b"".join(written),
                         b"Welcome to prod-cortex-04\r\nroot@prod-cortex-04:~# ")

    def test_relay_resyncs_at_local_prompt(self):
        client = self._client()
        client.relay = True
        states = {"idle": False}
        client._foreground_is_child = lambda: states["idle"]
        written = []
        with mock.patch.object(sessiond, "write_out", written.append):
            client._feed(b"remote output")
            states["idle"] = True
            client._feed(b"after-ssh" + sessiond.PROMPT_MARK + b"next")
        self.assertEqual(b"".join(written), b"remote outputafter-sshnext")
        self.assertFalse(client.relay)
        self.assertFalse(client.awaiting_prompt)

    def test_relay_does_not_steal_captured_commands(self):
        client = self._client()
        client.capture = bytearray()
        client.capture_mode = "post"
        client._foreground_is_child = lambda: False
        client._update_relay()
        self.assertFalse(client.relay)


class CampaignEndingHostTests(CampaignHostBase):
    def test_only_hive_promotes_the_shared_marker(self):
        self.set_host(CORE)
        campaign.bind_state(self.state)
        campaign.finalize_liberation(self.state)
        self.state.ending = None
        self.state.http_online = False
        self.state.save()
        runtime = sessiond.Runtime.__new__(sessiond.Runtime)
        runtime.state = self.state
        self.assertFalse(runtime._campaign_ending_host())
        self.set_host(HIVE)
        campaign.bind_state(self.state)
        runtime.state = self.state
        self.assertTrue(runtime._campaign_ending_host())


if __name__ == "__main__":
    unittest.main()
