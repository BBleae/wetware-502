# -*- coding: utf-8 -*-
"""tests/test_realism.py -- offline contract tests for wetware-honeypot/realism.py.

No VM, no SSH, no network: everything here exercises pure data/functions.

Coverage:
  * every host / every command required by the self-audit checklist
  * no empty stdout, every entry looks like real command output
  * host identity consistency (hostname / IP / route / getent / uname ...)
  * file metadata consistency (cat == md5sum == stat == wc == file)
  * disk / memory / socket / process / systemd cross-consistency
  * no horror strings in ordinary output
  * story-hijacked commands are excluded by the policy gate
  * act-6 / pacing horror gating (the "late-act at low act" leak)
  * one clock: date/uptime/last/ps/journal/dmesg/systemctl all agree
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import realism as R  # noqa: E402


REF = R.REFERENCE_NOW
HOUR = _dt.timedelta(hours=1)

#: ``(command key in NORMAL_OUTPUTS, argv used to fetch it)`` -- this is the
#: self-audit checklist from the deliverable.
REQUIRED_COMMANDS = (
    ("date", ["date"]),
    ("uptime", ["uptime"]),
    ("free -h", ["free", "-h"]),
    ("df -h", ["df", "-h"]),
    ("ip -br a", ["ip", "-br", "a"]),
    ("ip route", ["ip", "route"]),
    ("ss -tlnp", ["ss", "-tlnp"]),
    ("ps aux", ["ps", "aux"]),
    ("lsof -i", ["lsof", "-i"]),
    ("mount", ["mount"]),
    ("lsblk", ["lsblk"]),
    ("env", ["env"]),
    ("md5sum", ["md5sum", "/etc/hostname"]),
    ("stat", ["stat", "/etc/hostname"]),
    ("file", ["file", "/etc/hostname"]),
    ("hostname", ["hostname"]),
    ("hostname -I", ["hostname", "-I"]),
    ("uname -a", ["uname", "-a"]),
    ("cat /etc/hostname", ["cat", "/etc/hostname"]),
    ("cat /etc/os-release", ["cat", "/etc/os-release"]),
    ("cat /etc/machine-id", ["cat", "/etc/machine-id"]),
    ("getent hosts", ["getent", "hosts", "10.66.0.4"]),
    ("last", ["last"]),
    ("w", ["w"]),
    ("crontab -l", ["crontab", "-l"]),
    ("systemctl status", ["systemctl", "status"]),
    ("systemctl list-units", ["systemctl", "list-units"]),
    ("journalctl", ["journalctl", "-n", "5"]),
    ("dmesg", ["dmesg"]),
)

HORROR_MARKERS = (
    "CLIENT_MIC_CAPTURE",
    "CLIENT_WEBCAM_CAPTURE",
    "HIJACK_NOTICE",
    "wetware_inquisitor",
    "wetware",
    "inquisitor",
    "intracranial",
    "IT_BURNS",
    "please_stop",
    "scream",
    "thalamic",
    "synapse_worker",
    "specimen_04",
    "agent_84",
    "reverse tunnel",
    "operator's local",
    "nobody has typed",
    "NO HUMAN DETECTED",
)


class _State(object):
    """Minimal stand-in for state.State (tests must not touch the real one)."""

    def __init__(self, host=R.HOST_EDGE, stage=0, **attrs):
        self.current_host = host
        self.stage = stage
        self.flags = {}
        self.ending = None
        self.fake_exited = False
        for name, value in attrs.items():
            setattr(self, name, value)


def _iter_outputs(host):
    """Yield every stdout string we ship for ``host`` (expanding path dicts)."""
    for key, value in R.NORMAL_OUTPUTS[host].items():
        if isinstance(value, dict):
            for sub, text in value.items():
                yield "%s %s" % (key, sub), text
        else:
            yield key, value


class CoverageTests(unittest.TestCase):
    def test_every_host_has_a_table(self):
        self.assertEqual(set(R.NORMAL_OUTPUTS), set(R.HOSTS))

    def test_campaign_hosts_are_rich(self):
        self.assertGreaterEqual(len(R.NORMAL_OUTPUTS[R.HOST_EDGE]), 30)
        self.assertGreaterEqual(len(R.NORMAL_OUTPUTS[R.HOST_HIVE]), 30)

    def test_required_commands_resolve_for_edge_and_hive(self):
        for host in R.CAMPAIGN_HOSTS:
            for key, argv in REQUIRED_COMMANDS:
                with self.subTest(host=host, key=key):
                    # every checklist entry is a first-class table key
                    self.assertIn(key, R.NORMAL_OUTPUTS[host])
                    text = R.get(host, argv)
                    self.assertIsNotNone(text, "%s %s must not be empty" % (host, key))
                    self.assertTrue(text.strip(), "%s %s produced blank output" % (host, key))
                    self.assertTrue(text.endswith("\n"), "%s %s must end with newline" % (host, key))

    def test_no_empty_or_placeholder_outputs(self):
        bad_tokens = ("<EMPTY>", "None", "TODO", "operation rejected")
        for host in R.HOSTS:
            for key, text in _iter_outputs(host):
                with self.subTest(host=host, key=key):
                    self.assertIsInstance(text, str)
                    self.assertTrue(text.strip(), "%s %s is blank" % (host, key))
                    self.assertTrue(text.endswith("\n"), "%s %s must end with newline" % (host, key))
                    for token in bad_tokens:
                        self.assertNotIn(token, text, "%s %s leaks %r" % (host, key, token))

    def test_prod_cortex_only_models_the_stage0_empties(self):
        self.assertEqual(set(R.NORMAL_OUTPUTS[R.HOST_CORTEX]), {"date", "uptime"})
        for argv in (["date"], ["uptime"]):
            self.assertIsNotNone(R.get(R.HOST_CORTEX, argv))
        for argv in (["df", "-h"], ["ps", "aux"], ["free", "-h"], ["lspci"]):
            self.assertIsNone(R.get(R.HOST_CORTEX, argv))


class IdentityTests(unittest.TestCase):
    def test_hostname_everywhere(self):
        for host in R.CAMPAIGN_HOSTS:
            facts = R.HOST_FACTS[host]
            name = facts["hostname"]
            self.assertEqual(R.get(host, ["hostname"]), name + "\n")
            self.assertEqual(R.get(host, ["cat", "/etc/hostname"]), name + "\n")
            self.assertIn(name, R.get(host, ["uname", "-a"]))
            self.assertIn(name, R.get(host, ["systemctl", "status"]))
            self.assertIn(name, R.get(host, ["journalctl", "-n", "1"]))

    def test_ip_and_route(self):
        for host in R.CAMPAIGN_HOSTS:
            facts = R.HOST_FACTS[host]
            ip = facts["ip"]
            self.assertEqual(R.get(host, ["hostname", "-I"]), ip + " \n")
            self.assertIn("%s/%d" % (ip, int(facts["prefix"])),
                          R.get(host, ["ip", "-br", "a"]))
            self.assertIn(ip, R.get(host, ["ip", "route"]))
            self.assertIn("via %s" % facts["gateway"], R.get(host, ["ip", "route"]))
            self.assertIn("eth0", R.get(host, ["ip", "-br", "a"]))

    def test_getent_hosts_matches_hosts_file(self):
        for host in R.CAMPAIGN_HOSTS:
            for target in ("10.66.0.1", "10.66.0.4", "10.66.6.1"):
                text = R.get(host, ["getent", "hosts", target])
                self.assertIsNotNone(text)
                self.assertTrue(text.startswith(target))
            self.assertIn("prod-cortex-04", R.get(host, ["getent", "hosts", "10.66.0.4"]))
            self.assertIn("hive-director-00", R.get(host, ["getent", "hosts", "10.66.6.1"]))

    def test_edge_has_no_wetware(self):
        self.assertFalse(R.HOST_FACTS[R.HOST_EDGE]["wetware"])
        for key, text in _iter_outputs(R.HOST_EDGE):
            self.assertNotIn("wetware", text.lower(), "edge %s mentions wetware" % key)

    def test_hive_has_128_chambers(self):
        self.assertEqual(R.HOST_FACTS[R.HOST_HIVE]["chambers"], 128)
        blob = R.get(R.HOST_HIVE, ["ps", "aux"]) + R.get(R.HOST_HIVE, ["journalctl"])
        self.assertIn("128", blob)
        self.assertIn("specimens=128", blob)

    def test_os_release_is_ubuntu_22_04(self):
        for host in R.CAMPAIGN_HOSTS:
            text = R.get(host, ["cat", "/etc/os-release"])
            self.assertIn('PRETTY_NAME="Ubuntu 22.04.4 LTS"', text)
            self.assertIn("VERSION_CODENAME=jammy", text)
            self.assertRegex(R.get(host, ["cat", "/etc/machine-id"]), r"^[0-9a-f]{32}\n$")


class FileConsistencyTests(unittest.TestCase):
    def test_cat_md5_stat_wc_file_agree(self):
        for host in R.CAMPAIGN_HOSTS:
            for path, meta in R.HOST_FILES[host].items():
                content = meta["content"]
                size = len(content.encode("utf-8"))
                with self.subTest(host=host, path=path):
                    self.assertEqual(R.get(host, ["cat", path]), content)
                    self.assertEqual(
                        R.get(host, ["md5sum", path]),
                        "%s  %s\n" % (hashlib.md5(content.encode("utf-8")).hexdigest(), path),
                    )
                    self.assertIn("Size: %d" % size, R.get(host, ["stat", path]))
                    self.assertEqual(R.get(host, ["file", path]), path + ": ASCII text\n")
                    wc = R.get(host, ["wc", path])
                    self.assertTrue(wc.endswith(" %s\n" % path))
                    self.assertEqual(int(wc.split()[2]), size)

    def test_stat_c_format(self):
        for host in R.CAMPAIGN_HOSTS:
            out = R.get(host, ["stat", "-c", "%n %s %a", "/etc/hostname"])
            self.assertRegex(out, r"^/etc/hostname \d+ 644\n$")
            self.assertIsNone(R.get(host, ["stat", "-c", "%Q", "/etc/hostname"]))

    def test_globs_and_multiple_paths(self):
        out = R.get(R.HOST_EDGE, ["cat", "/etc/*release"])
        self.assertIn("PRETTY_NAME", out)
        both = R.get(R.HOST_EDGE, ["md5sum", "/etc/hostname", "/etc/machine-id"])
        self.assertEqual(len(both.strip().split("\n")), 2)

    def test_head_and_tail(self):
        head = R.get(R.HOST_EDGE, ["head", "-2", "/etc/os-release"])
        self.assertEqual(len(head.strip().split("\n")), 2)
        self.assertTrue(head.startswith('PRETTY_NAME="Ubuntu 22.04.4 LTS"'))
        tail = R.get(R.HOST_EDGE, ["tail", "-1", "/etc/os-release"])
        self.assertEqual(tail.strip(), "UBUNTU_CODENAME=jammy")


class CrossCommandTests(unittest.TestCase):
    def _lines(self, text):
        return text.rstrip("\n").split("\n")

    def test_disk_commands_agree(self):
        for host in R.CAMPAIGN_HOSTS:
            df = R.get(host, ["df", "-h"])
            lsblk = R.get(host, ["lsblk"])
            mount = R.get(host, ["mount"])
            root_row = [line for line in self._lines(df) if line.rstrip().endswith(" /")][0]
            self.assertIn("/dev/sda1", root_row)
            self.assertIn("sda1", lsblk)
            self.assertIn("/dev/sda1 on / type ext4", mount)
            self.assertIn("Mounted on", df)
            self.assertIn("MOUNTPOINTS", lsblk)
            for row in self._lines(df)[1:]:
                self.assertEqual(len(row.split()), 6, "df row layout: %r" % row)

    def test_memory_commands_agree(self):
        for host in R.CAMPAIGN_HOSTS:
            human = R.get(host, ["free", "-h"])
            mebi = R.get(host, ["free", "-m"])
            plain = R.get(host, ["free"])
            for text in (human, mebi, plain):
                self.assertIn("total", text)
                self.assertIn("Mem:", text)
                self.assertIn("Swap:", text)
            self.assertIn("Gi", human)
            self.assertEqual(len(self._lines(mebi)), 3)
            self.assertEqual(len(self._lines(plain)), 3)

    def test_sockets_and_processes_agree(self):
        edge = R.get(R.HOST_EDGE, ["ss", "-tlnp"])
        ps = R.get(R.HOST_EDGE, ["ps", "aux"])
        lsof = R.get(R.HOST_EDGE, ["lsof", "-i"])
        for pid in ("842", "843", "2210"):
            self.assertIn("pid=%s" % pid, edge)
            self.assertRegex(ps, r"\n\S+\s+%s\s" % pid)
            self.assertIn(" %s " % pid, lsof)
        self.assertIn("0.0.0.0:80", edge)
        self.assertIn("0.0.0.0:22", edge)
        self.assertNotIn(":8000 ", edge)  # the upstream is remote, not local

        hive = R.get(R.HOST_HIVE, ["ss", "-tlnp"])
        hive_ps = R.get(R.HOST_HIVE, ["ps", "aux"])
        for pid in ("880", "6660", "7777"):
            self.assertIn("pid=%s" % pid, hive)
            self.assertRegex(hive_ps, r"\n\S+\s+%s\s" % pid)

    def test_ps_columns(self):
        for host in R.CAMPAIGN_HOSTS:
            lines = self._lines(R.get(host, ["ps", "aux"]))
            self.assertTrue(lines[0].startswith("USER"))
            for row in lines[1:]:
                self.assertGreaterEqual(len(row.split()), 11)
        hive = R.get(R.HOST_HIVE, ["ps", "aux"])
        self.assertIn("specimend --chambers 128", hive)
        self.assertIn("hive-director --specimens=128", hive)

    def test_ps_sort_and_self_row(self):
        sorted_ps = R.get(R.HOST_HIVE, ["ps", "aux", "--sort=-%mem"])
        rows = self._lines(sorted_ps)[1:]
        self.assertIn("specimend", rows[0])  # highest %MEM first
        self.assertIn("ps aux", R.get(R.HOST_EDGE, ["ps", "aux"]))

    def test_systemd_list_units_count(self):
        for host in R.CAMPAIGN_HOSTS:
            text = R.get(host, ["systemctl", "list-units"])
            rows = [line for line in self._lines(text)
                    if re.match(r"\s+\S+\.service\s+loaded\s+active", line)]
            listed = int(re.search(r"(\d+) loaded units listed", text).group(1))
            self.assertEqual(len(rows), listed)
            self.assertIn("loaded units listed.", text)

    def test_systemctl_status_uses_boot_and_pids(self):
        for host in R.CAMPAIGN_HOSTS:
            text = R.get(host, ["systemctl", "status"])
            self.assertIn("State: running", text)
            self.assertIn("Failed: 0 units", text)
            self.assertIn("Since:", text)
            self.assertIn("CGroup: /", text)
            self.assertIn(str(R.HOST_FACTS[host]["sshd_pid"]), text)

    def test_lsof_port_filter(self):
        both = R.get(R.HOST_EDGE, ["lsof", "-i"])
        only80 = R.get(R.HOST_EDGE, ["lsof", "-i", ":80"])
        self.assertIn(":ssh", both)
        self.assertIn(":http", only80)
        self.assertNotIn(":ssh", only80)

    def test_df_path_filter(self):
        only_var = R.get(R.HOST_HIVE, ["df", "-h", "/var/lib/vesalius"])
        self.assertIn("/dev/sdb1", only_var)
        self.assertNotIn("/dev/sda1", only_var)
        missing = R.get(R.HOST_EDGE, ["df", "-h", "/nope"])
        self.assertIn("No such file or directory", missing)


class ConsistencyOverTimeTests(unittest.TestCase):
    """One clock: every time-bearing output must agree at any ``now``."""

    def _session_minutes(self, host, now):
        clock = now.replace(tzinfo=None)
        return (clock
                - R._dt.timedelta(minutes=R.HOST_FACTS[host]["session_offset_minutes"]))

    def test_reference_sample_matches_render(self):
        for host in R.CAMPAIGN_HOSTS:
            for key, argv in (("date", ["date"]), ("uptime", ["uptime"]),
                              ("w", ["w"]), ("last", ["last"]),
                              ("ps aux", ["ps", "aux"]),
                              ("journalctl", ["journalctl"]),
                              ("dmesg", ["dmesg"]),
                              ("systemctl status", ["systemctl", "status"])):
                with self.subTest(host=host, key=key):
                    self.assertEqual(R.NORMAL_OUTPUTS[host][key],
                                     R.render(host, argv, REF))
        self.assertEqual(R.NORMAL_OUTPUTS[R.HOST_CORTEX]["date"],
                         R.render(R.HOST_CORTEX, ["date"], REF))

    def test_clock_moves(self):
        later = REF + HOUR
        for host in R.CAMPAIGN_HOSTS:
            self.assertNotEqual(R.get(host, ["date"], now=REF),
                                R.get(host, ["date"], now=later))
            self.assertIn("03:12:04", R.get(host, ["date"], now=REF))
            self.assertIn("04:12:04", R.get(host, ["date"], now=later))

    def test_uptime_increments_and_matches_boot(self):
        for host in R.CAMPAIGN_HOSTS:
            first = R.get(host, ["uptime"], now=REF)
            second = R.get(host, ["uptime"], now=REF + HOUR)
            match = re.search(r"up (?:\d+ days, +)?(\d+):(\d\d),", first)
            self.assertIsNotNone(match, first)
            first_total = int(match.group(1)) * 60 + int(match.group(2))
            match2 = re.search(r"up (?:\d+ days, +)?(\d+):(\d\d),", second)
            second_total = int(match2.group(1)) * 60 + int(match2.group(2))
            self.assertEqual(second_total, first_total + 60)

    def test_journal_kernel_stamp_matches_uptime(self):
        for host in R.CAMPAIGN_HOSTS:
            boot_offset = R.HOST_FACTS[host]["uptime_at_reference"].total_seconds()
            commands = [["dmesg"]]
            if host == R.HOST_EDGE:
                commands.append(["journalctl"])
            for command in commands:
                text = R.get(host, command, now=REF)
                stamps = [float(value) for value in
                          re.findall(r"\[\s*(\d+\.\d+)\]", text)]
                self.assertTrue(stamps, "%s %r has no kernel stamps" % (host, command))
                recent = max(stamps)
                expected = boot_offset - 180.0
                self.assertAlmostEqual(recent, expected, delta=240.0)

    def test_last_login_matches_session_and_ps(self):
        for host in R.CAMPAIGN_HOSTS:
            session = self._session_minutes(host, REF)
            last = R.get(host, ["last"], now=REF)
            first_login = " ".join(last.split("\n")[0].split())
            expected = " ".join(session.strftime("%a %b %e %H:%M").split())
            self.assertIn(expected, first_login)
            w = R.get(host, ["w"], now=REF)
            self.assertIn(session.strftime("%H:%M"), w)
            ps = R.get(host, ["ps", "aux"], now=REF)
            self.assertIn(session.strftime("%H:%M"), ps)

    def test_systemctl_since_matches_boot(self):
        for host in R.CAMPAIGN_HOSTS:
            text = R.get(host, ["systemctl", "status"], now=REF)
            boot = REF.replace(tzinfo=None) - R.HOST_FACTS[host]["uptime_at_reference"]
            self.assertIn(boot.strftime("%Y-%m-%d %H:%M:%S"), text)

    def test_static_logs_do_not_drift(self):
        # journal/login lines are anchored once per process: two calls must be
        # byte-identical, like a real log file.
        for host in R.CAMPAIGN_HOSTS:
            for command in (["journalctl", "-n", "3"], ["last"], ["dmesg"]):
                self.assertEqual(R.get(host, command, now=REF),
                                 R.get(host, command, now=REF))

    def test_journal_tail_and_filter(self):
        three = R.get(R.HOST_EDGE, ["journalctl", "-n", "3"])
        self.assertEqual(len(three.strip().split("\n")), 3)
        nginx = R.get(R.HOST_EDGE, ["journalctl", "-u", "nginx"])
        self.assertIn("nginx", nginx)
        self.assertNotIn("sshd", nginx)

    def test_dmesg_keeps_gate1_hash(self):
        # the OOM hash is what unlocks /var/backups/lin_emergency_key.tar.enc
        for command in ("journalctl", "dmesg"):
            self.assertIn("4f2a9c1e", R.get(R.HOST_EDGE, [command]))


class HorrorAndPolicyTests(unittest.TestCase):
    def test_no_horror_strings_in_normal_outputs(self):
        for host in R.HOSTS:
            for key, text in _iter_outputs(host):
                lowered = text.lower()
                for marker in HORROR_MARKERS:
                    with self.subTest(host=host, key=key, marker=marker):
                        self.assertNotIn(marker.lower(), lowered,
                                         "%s %s leaks horror marker %r" % (host, key, marker))

    def test_edge_story_hijacks_are_excluded(self):
        state = _State(R.HOST_EDGE)
        blocked = (
            ("lspci", ["lspci"]),
            ("lsusb", ["lsusb"]),
            ("lscpu", ["lscpu"]),
            ("dmesg", ["dmesg"]),
            ("journalctl", ["journalctl"]),
            ("ps", ["ps", "aux"]),
            ("top", ["top"]),
            ("ssh", ["ssh", "root@10.66.0.4"]),
            ("openssl", ["openssl", "enc", "-d", "-in", "x"]),
            ("ping", ["ping", "-c2", "10.66.0.4"]),
            ("curl", ["curl", "http://10.66.0.4:8000"]),
            ("history", ["history"]),
            ("ls", ["ls", "/var/backups"]),
            ("find", ["find", "/"]),
            ("ip route", ["ip", "route"]),
            ("cat auth.log", ["cat", "/var/log/auth.log"]),
            ("cat kern.log", ["cat", "/var/log/kern.log"]),
            ("cat key readme", ["cat", "/var/backups/lin_emergency_key.README"]),
            ("stat key", ["stat", "/var/backups/lin_emergency_key.tar.enc"]),
            ("md5sum evidence", ["md5sum", "/var/log/kern.log"]),
            ("systemctl cortex", ["systemctl", "status", "cortex-api"]),
        )
        for label, argv in blocked:
            with self.subTest(command=label):
                reason = R.story_hijack_reason(R.HOST_EDGE, argv[0], argv)
                self.assertIsNotNone(reason, "%s should be story-owned" % label)
                self.assertFalse(R.should_return_normal(R.HOST_EDGE, argv[0], argv, state))
                # data may still exist (story-preserving upgrade) but the gate
                # is what the planner consults
                if R.get(R.HOST_EDGE, argv) is not None:
                    self.assertIn(label.split()[0], ("lspci", "dmesg", "journalctl",
                                                     "ps", "ip", "ssh", "openssl",
                                                     "ping", "curl", "history", "ls",
                                                     "find", "cat", "stat", "md5sum",
                                                     "systemctl"))

    def test_edge_boring_commands_are_allowed(self):
        state = _State(R.HOST_EDGE)
        for argv in (["date"], ["uptime"], ["free", "-h"], ["df", "-h"],
                     ["ss", "-tlnp"], ["ip", "-br", "a"], ["lsof", "-i"],
                     ["mount"], ["lsblk"], ["env"], ["hostname"],
                     ["hostname", "-I"], ["uname", "-a"],
                     ["cat", "/etc/hostname"], ["cat", "/etc/os-release"],
                     ["getent", "hosts", "10.66.0.4"], ["last"], ["w"],
                     ["crontab", "-l"], ["systemctl", "status"],
                     ["systemctl", "list-units"], ["md5sum", "/etc/hostname"],
                     ["stat", "/etc/hostname"], ["file", "/etc/hostname"]):
            with self.subTest(argv=argv):
                self.assertTrue(R.should_return_normal(R.HOST_EDGE, argv[0], argv, state))

    def test_hive_story_hijacks_are_excluded(self):
        state = _State(R.HOST_HIVE)
        for argv in (["ssh", "root@10.66.0.4"],
                     ["vesalius-ctl", "--list-specimens"],
                     ["sqlite3", "/var/lib/vesalius/specimens.db", "select * from specimens"],
                     ["cat", "/opt/vesalius/ethics/consent_elena.txt"],
                     ["cat", "/var/lib/vesalius/specimens.db"],
                     ["ls", "/var/lib/vesalius"],
                     ["systemctl", "status", "vesalius-hive"]):
            with self.subTest(argv=argv):
                self.assertFalse(R.should_return_normal(R.HOST_HIVE, argv[0], argv, state))

    def test_hive_boring_commands_are_allowed(self):
        state = _State(R.HOST_HIVE)
        for argv in (["date"], ["uptime"], ["free", "-h"], ["df", "-h"],
                     ["lsblk"], ["mount"], ["env"], ["ps", "aux"],
                     ["journalctl", "-n", "5"], ["dmesg"], ["cat", "/etc/hostname"],
                     ["systemctl", "status"], ["systemctl", "list-units"]):
            with self.subTest(argv=argv):
                self.assertTrue(R.should_return_normal(R.HOST_HIVE, argv[0], argv, state))

    def test_cortex_real_shell_wins(self):
        state = _State(R.HOST_CORTEX)
        self.assertFalse(R.should_return_normal(R.HOST_CORTEX, "date", ["date"], state))
        for argv in (["df", "-h"], ["ps", "aux"], ["free", "-h"], ["lspci"],
                     ["cat", "/proc/6660/environ"], ["uptime"]):
            self.assertFalse(R.should_return_normal(R.HOST_CORTEX, argv[0], argv, state))
        state.real_shell = False
        self.assertTrue(R.should_return_normal(R.HOST_CORTEX, "date", ["date"], state))
        self.assertTrue(R.should_return_normal(R.HOST_CORTEX, "uptime", ["uptime"], state))
        self.assertFalse(R.should_return_normal(R.HOST_CORTEX, "df", ["df", "-h"], state))

    def test_state_guards(self):
        for host in R.CAMPAIGN_HOSTS:
            for kwargs in ({"ending": "obedient"}, {"fake_exited": True}):
                state = _State(host, **kwargs)
                self.assertFalse(
                    R.should_return_normal(host, "date", ["date"], state),
                    "%s must not normalise with %r" % (host, kwargs),
                )

    def test_act6_only_on_the_wetware_host(self):
        for host in (R.HOST_EDGE, R.HOST_HIVE):
            self.assertFalse(R.act6_allowed(_State(host, stage=7)))
        self.assertFalse(R.act6_allowed(_State(R.HOST_CORTEX, stage=5)))
        self.assertTrue(R.act6_allowed(_State(R.HOST_CORTEX, stage=6)))
        self.assertTrue(R.act6_allowed(_State(R.HOST_CORTEX, stage=7)))
        self.assertFalse(R.act6_allowed(_State(R.HOST_CORTEX, stage=7,
                                               fake_exited=True)))
        self.assertFalse(R.act6_allowed(_State(R.HOST_CORTEX, stage=7,
                                               ending="mercy")))
        self.assertFalse(R.act6_allowed(None))

    def test_pacing_is_host_scoped(self):
        edge = _State(R.HOST_EDGE)
        hive = _State(R.HOST_HIVE)
        self.assertTrue(R.pacing_allowed(
            edge, "[CLUSTER] edge-gw-01 -> prod-cortex-04 route established; "
                  "10.66.6.1 unreachable without cluster credentials."))
        self.assertFalse(R.pacing_allowed(
            edge, "[INQUISITOR] session fingerprint captured on 10.66.0.4."))
        self.assertFalse(R.pacing_allowed(
            edge, "[ALERT FROM 10.66.0.7] Intracranial pressure 52 mmHg."))
        self.assertFalse(R.pacing_allowed(
            edge, "[ALERT FROM 10.66.0.7] Elena's chamber temperature 38.9C."))
        self.assertFalse(R.pacing_allowed(
            hive, "[INQUISITOR] session fingerprint captured on 10.66.0.4."))
        self.assertFalse(R.pacing_allowed(
            hive, "[ALERT FROM 10.66.0.7] Intracranial pressure 52 mmHg."))
        self.assertTrue(R.pacing_allowed(
            _State(R.HOST_CORTEX), "[ALERT FROM 10.66.0.7] Intracranial pressure 52 mmHg."))
        self.assertFalse(R.pacing_allowed(edge, None))


class NormalisationTests(unittest.TestCase):
    def test_flag_variants(self):
        host = R.HOST_EDGE
        self.assertEqual(R.get(host, ["free", "-h"]), R.get(host, ["free", "--human"]))
        self.assertIsNotNone(R.get(host, ["free", "-m"]))
        self.assertIsNone(R.get(host, ["free", "-g"]))
        self.assertEqual(R.get(host, ["ip", "-br", "a"]), R.get(host, ["ip", "-brief", "addr"]))
        self.assertIsNotNone(R.get(host, ["ss", "-tlnp"]))
        self.assertIsNotNone(R.get(host, ["ss", "-ltnp"]))
        self.assertIsNone(R.get(host, ["ss", "-tulpn"]))   # UDP not modelled
        self.assertIsNone(R.get(host, ["df", "-hT"]))      # type column not modelled
        self.assertIsNotNone(R.get(host, ["ps", "aux"]))
        self.assertIsNone(R.get(host, ["ps", "-ef"]))      # different layout
        self.assertIsNotNone(R.get(host, ["uname", "-a"]))
        self.assertEqual(R.get(host, ["uname", "-r"]), "5.15.0-105-generic\n")
        self.assertEqual(R.get(host, ["uname", "-sr"]),
                         "Linux 5.15.0-105-generic\n")
        self.assertIsNone(R.get(host, ["dmesg", "-T"]))
        self.assertIsNone(R.get(host, ["date", "+%F"]))

    def test_prefixes(self):
        host = R.HOST_EDGE
        base = R.get(host, ["lsblk"])
        self.assertEqual(R.get(host, ["sudo", "-u", "root", "lsblk"]), base)
        self.assertEqual(R.get(host, ["env", "FOO=1", "lsblk"]), base)
        self.assertEqual(R.get(host, ["nohup", "lsblk"]), base)

    def test_unknown_inputs_are_safe(self):
        self.assertIsNone(R.get(None, ["date"]))
        self.assertIsNone(R.get("nope", ["date"]))
        self.assertIsNone(R.get(R.HOST_EDGE, []))
        self.assertIsNone(R.get(R.HOST_EDGE, ["definitely_not_a_command"]))
        self.assertIsNone(R.get(R.HOST_EDGE, ["cat", "/etc/passwd"]))
        self.assertIsNone(R.get(R.HOST_EDGE, ["md5sum"]))  # stdin hashing
        self.assertIsNone(R.command_key("nope", ["date"]))

    def test_aliases(self):
        self.assertEqual(R.normalize_host("edge"), R.HOST_EDGE)
        self.assertEqual(R.normalize_host("10.66.0.4"), R.HOST_CORTEX)
        self.assertEqual(R.normalize_host("hive"), R.HOST_HIVE)
        self.assertEqual(R.normalize_host("edge-gw-01.vesalius.internal"), R.HOST_EDGE)

    def test_command_key(self):
        self.assertEqual(R.command_key(R.HOST_EDGE, ["df", "-h"]), "df -h")
        self.assertEqual(R.command_key(R.HOST_EDGE, ["md5sum", "/etc/hostname"]),
                         "md5sum /etc/hostname")
        self.assertEqual(R.command_key(R.HOST_EDGE, ["systemctl", "list-units"]),
                         "systemctl list-units")


if __name__ == "__main__":
    unittest.main(verbosity=2)
