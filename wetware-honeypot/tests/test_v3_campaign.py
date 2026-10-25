# -*- coding: utf-8 -*-
"""Offline tests for the v3.0 campaign expansion (no VM required)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import commands  # noqa: E402
import shell_parser  # noqa: E402
import state  # noqa: E402
import v3  # noqa: E402


class CampaignFlow(unittest.TestCase):
    def setUp(self):
        self.state = state.State(path="/tmp/wetware-v3-test-state.json")
        self.state.reset()
        self.state.flags["campaign_v3"] = True
        self.state.current_host = "edge-gw-01"
        self.state.stage = 0
        self.state.cmd_count = 0

    def run_cmd(self, line):
        parsed = shell_parser.parse_line(line)
        plan = commands.plan(self.state, parsed, "exec")
        effects = []
        for seg in plan.segs:
            effects.extend(seg.effects or [])
            if seg.session_action:
                self.action = seg.session_action
        commands.apply_effects(self.state, effects)
        v3.after_command(self.state, line)
        self.state.cmd_count += 1
        return "".join((seg.stdout or "") for seg in plan.segs), plan

    def test_gate1_key_and_jump(self):
        self.run_cmd("cat /var/log/auth.log")
        self.run_cmd("cat /var/log/kern.log")
        self.run_cmd("cat /var/backups/lin_emergency_key.README")
        out, _ = self.run_cmd("openssl enc -d -aes-256-cbc -pbkdf2 -in /var/backups/lin_emergency_key.tar.enc -out /tmp/lin.tar -k 4f2a9c1e")
        self.assertIn("id_ed25519_cortex", out)
        self.assertTrue(self.state.flags.get("gate1_key_obtained"))
        self.run_cmd("ssh -i /root/.ssh/id_ed25519_cortex root@10.66.0.4")
        self.assertEqual(self.state.current_host, "prod-cortex-04")

    def test_gate1_requires_recon(self):
        out, _ = self.run_cmd("openssl enc -d -aes-256-cbc -in /var/backups/lin_emergency_key.tar.enc -k 4f2a9c1e -out /tmp/x")
        self.assertIn("passphrase required", out)
        self.assertFalse(self.state.flags.get("gate1_key_obtained"))

    def test_gate2_warning_and_token(self):
        self.state.current_host = "prod-cortex-04"
        self.run_cmd("systemctl stop cortex-api")
        self.assertTrue(self.state.flags.get("cluster_warned"))
        self.assertTrue(self.state.pending_events)
        out, _ = self.run_cmd("cat /proc/6660/environ")
        self.assertIn("HIVE_ADMIN_TOKEN", out)
        self.assertTrue(self.state.flags.get("gate3_token"))
        self.run_cmd("ssh root@10.66.6.1")
        self.assertEqual(self.state.current_host, "hive-director-00")

    def test_dynamic_override_and_liberation(self):
        self.state.current_host = "hive-director-00"
        self.state.flags["gate3_token"] = True
        out, _ = self.run_cmd("cat /opt/vesalius/ethics/consent_elena.txt")
        self.assertIn("chamber_07", out)
        expected = v3.override_code_expected()
        out, _ = self.run_cmd('echo %s > /sys/kernel/vesalius/metabolic_override' % expected)
        self.assertIn("metabolic coupling watchdog disabled", out)
        self.assertTrue(self.state.flags.get("override_code"))
        self.run_cmd("vesalius-ctl --spin-up-silicon-mirror --all-nodes")
        out, plan = self.run_cmd("vesalius-ctl --global-cryo-stasis --authorize-dnr --broadcast-blackbox")
        self.assertIn("global cryo-stasis", out)
        self.assertEqual(plan.segs[-1].session_action, "ending_liberation")

    def test_override_rejects_wrong_code(self):
        self.state.current_host = "hive-director-00"
        self.run_cmd("echo WRONGCODE > /sys/kernel/vesalius/metabolic_override")
        self.assertFalse(self.state.flags.get("override_code"))

    def test_hive_evidence(self):
        self.state.current_host = "hive-director-00"
        out, _ = self.run_cmd("vesalius-ctl --specimens 7")
        self.assertIn("Elena", out)
        out, _ = self.run_cmd("vesalius-ctl --evidence")
        self.assertIn("agent_84", out)

    def test_tty_dialogue(self):
        self.state.current_host = "prod-cortex-04"
        out, _ = self.run_cmd("echo help > /dev/wetware_tty0")
        self.assertIn("10.66.6.1", out)
        self.assertTrue(self.state.flags.get("tty_contact"))

    def test_selfish_ending_queued(self):
        self.state.current_host = "prod-cortex-04"
        self.state.flags["cluster_warned"] = True
        self.run_cmd("euthanize_wetware --specimen=subject_04 --override-mission")
        self.assertEqual(self.state.flags.get("pending_ending"), "selfish")


if __name__ == "__main__":
    unittest.main()
