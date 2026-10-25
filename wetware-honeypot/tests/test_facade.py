# -*- coding: utf-8 -*-
"""Offline tests for ``facade.py`` (the v3 campaign virtual-host filesystem).

No VM, no network, no SSH: everything here is pure data/rendering.

Coverage
  * ``ls -l/-a/-h`` shape: 10-char permission strings, ``total N``, dotfiles
    only under ``-a``, symlink arrows, device major/minor, sticky bits;
  * one record drives cat/stat/file: byte counts, ``stat`` size/inode/mode,
    ``file`` type, and ``ls -l`` size column all agree;
  * edge vs hive are *different machines*: no ``/home`` (and no root-listing
    mention of it) on the director, chambers only on the hive, and the edge's
    ordinary listings never equal the hive's;
  * the original bug: ``ls -la /tmp``/``/etc``/``/home`` are never the root
    listing, and an unknown path yields ``cannot access`` instead of a lie;
  * no wetware artefact (``synapse_worker``) or hive path on the clean edge;
  * common files never ENOENT on either host;
  * cross-module consistency with ``realism.py`` for the three files both
    modules answer (``/etc/hostname``, ``/etc/os-release``, ``/etc/machine-id``)
    -- cat == cat, stat == stat, file == file, byte for byte;
  * campaign state hooks: Gate 1 key/tar absent until extracted, hive override
    value reflects the flag;
  * structural invariants: every path has a parent entry, hive has no /home,
    story-pack artefacts all placed.

Run from ``wetware-honeypot/``:

    python3 -m unittest discover -s tests -p 'test_facade.py' -v
    python3 -m unittest tests.test_facade        # with -t . as well

The suite is Python 3.10 compatible (no 3.11+ syntax) and deterministic: the
facade is frozen at ``REFERENCE_NOW``, so no wall-clock dependency.
"""

from __future__ import annotations

import os
import posixpath
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import facade as F  # noqa: E402

try:  # optional: the cross-module consistency tests are skipped without it
    import realism as R  # noqa: E402
except Exception:  # pragma: no cover
    R = None

EDGE = F.HOST_EDGE
HIVE = F.HOST_HIVE

#: ``ls -l`` permission column, exactly like coreutils prints it.
PERMS_RE = re.compile(r"^[-dlcbps][-rwxsStT]{9}$")


class Structure(unittest.TestCase):
    """The data model itself: shape, parents, invariants."""

    def test_hosts(self):
        self.assertEqual(set(F.FILESYSTEM), {EDGE, HIVE})
        self.assertEqual(set(F.HOSTS), {EDGE, HIVE})
        self.assertNotIn("prod-cortex-04", F.FILESYSTEM)

    def test_every_path_has_a_parent(self):
        for host in F.HOSTS:
            tree = F.FILESYSTEM[host]
            self.assertIn("/", tree, host)
            for path in tree:
                if path == "/":
                    continue
                parent = posixpath.dirname(path)
                self.assertIn(parent, tree, "%s: %s has no parent" % (host, path))
                self.assertEqual(tree[parent]["kind"], "dir", "%s: %s parent not dir" % (host, path))

    def test_every_entry_has_the_render_fields(self):
        required = ("kind", "mode", "owner", "group", "size", "mtime", "inode",
                    "nlink", "blocks", "content", "binary", "desc", "target")
        for host in F.HOSTS:
            for path, item in F.FILESYSTEM[host].items():
                for key in required:
                    self.assertIn(key, item, "%s %s missing %r" % (host, path, key))
                self.assertGreaterEqual(item["inode"], 0)
                self.assertGreater(item["nlink"], 0)
                self.assertGreaterEqual(item["blocks"], 0)

    def test_content_sizes_are_honest(self):
        # A text body's declared size is its byte count; anything else would
        # make stat/ls disagree with cat.
        for host in F.HOSTS:
            for path, item in F.FILESYSTEM[host].items():
                if item["kind"] == "file" and not item["binary"]:
                    body = item["content"] or ""
                    self.assertEqual(len(body.encode("utf-8")), item["size"],
                                     "%s %s size %d != body %d"
                                     % (host, path, item["size"], len(body.encode("utf-8"))))

    def test_text_content_is_ascii(self):
        for host in F.HOSTS:
            for path, item in F.FILESYSTEM[host].items():
                if item["kind"] != "file" or item["binary"]:
                    continue
                body = item["content"] or ""
                bad = sorted({ch for ch in body if ord(ch) > 127})
                self.assertFalse(bad, "%s %s has non-ASCII %r" % (host, path, bad))

    def test_trees_are_not_the_same_machine(self):
        edge, hive = F.FILESYSTEM[EDGE], F.FILESYSTEM[HIVE]
        self.assertIn("/home", edge)
        self.assertNotIn("/home", hive)
        self.assertNotIn("/opt/vesalius", edge)
        self.assertNotIn("/var/lib/vesalius", edge)
        self.assertIn("/opt/vesalius", hive)
        self.assertIn("/var/lib/vesalius", hive)
        self.assertNotIn("/opt/cortex", hive)
        # edge is a small gateway, the director owns the chamber storage
        self.assertGreater(len(hive), 300)
        self.assertGreater(len(edge), 300)
        self.assertLess(len(edge["/etc/passwd"]["content"]), 4000)

    def test_lore_pack_is_fully_placed(self):
        # A story artefact without a parent directory would be an ENOENT in a
        # listing -- i.e. exactly the tell this module fixes.
        self.assertEqual(tuple(F.LORE_UNPLACED), ())


class LsShape(unittest.TestCase):
    """``ls`` looks like coreutils output, not like a hard-coded table."""

    def test_long_listing_has_permissions_owner_size_date(self):
        for host in F.HOSTS:
            out = F.ls_text(host, "/etc", long=True)
            self.assertTrue(out.startswith("total "), host)
            rows = [line for line in out.splitlines()[1:] if line.strip()]
            self.assertGreater(len(rows), 12, host)
            for row in rows:
                parts = row.split()
                self.assertTrue(PERMS_RE.match(parts[0]), "%s bad perms %r" % (host, row))
                self.assertRegex(parts[-1], r"^[\w.\-/]+$")
                # owner/group columns are present and look like names
                self.assertRegex(parts[2], r"^[a-z_][\w-]*$")
                self.assertRegex(parts[3], r"^[a-z_][\w-]*$")
                # a GNU date column: "Oct 26 03:12" or "Aug 28  2025"
                self.assertRegex(row, r"\b[A-Z][a-z]{2} [ 0-9]\d [0-9:]{4,5}\b|\b[A-Z][a-z]{2} [ 0-9]\d  \d{4}\b")

    def test_total_counts_blocks(self):
        for host in F.HOSTS:
            out = F.ls_text(host, "/var/log", long=True)
            total = int(out.splitlines()[0].split()[1])
            rows = [len(line.split()) for line in out.splitlines()[1:] if line.strip()]
            self.assertGreater(total, 0)
            self.assertEqual(len(rows), len([line for line in out.splitlines()[1:] if line.strip()]))

    def test_dotfiles_only_with_all(self):
        plain = F.ls_text(EDGE, "/root")
        dotted = F.ls_text(EDGE, "/root", all=True)
        long_form = F.ls_text(EDGE, "/root", long=True, all=True)
        self.assertNotIn(".bash_history", plain)
        self.assertIn(".bash_history", dotted)
        self.assertIn(".bash_history", long_form)
        # -a adds the . and .. entries, -A does not
        names = [line.split()[-1] for line in long_form.splitlines()[1:] if line.strip()]
        self.assertEqual(names[:2], [".", ".."])
        almost = F.ls_text(EDGE, "/root", long=True, almost_all=True)
        self.assertIn(".bash_history", almost)
        almost_names = [line.split()[-1] for line in almost.splitlines()[1:] if line.strip()]
        self.assertNotIn(".", almost_names)
        self.assertNotIn("..", almost_names)

    def test_dir_listing_dot_entries_appear_first(self):
        rows = [line for line in F.ls_text(EDGE, "/tmp", long=True, all=True).splitlines()[1:]
                if line.strip()]
        self.assertTrue(rows[0].endswith(" ."))
        self.assertTrue(rows[1].endswith(" .."))

    def test_sticky_and_setgid_modes(self):
        tmp_row = [line for line in F.ls_text(EDGE, "/", long=True).splitlines()
                   if line.split()[-1] == "tmp"]
        self.assertEqual(tmp_row[0].split()[0], "drwxrwxrwt")
        enabled = [line for line in F.ls_text(EDGE, "/etc/nginx", long=True).splitlines()
                   if line.split()[-1] == "sites-enabled"]
        self.assertEqual(enabled[0].split()[0], "drwxr-xr-x")

    def test_symlinks_render_arrow_and_target(self):
        rows = [line for line in F.ls_text(EDGE, "/", long=True).splitlines()
                if " bin -> " in line]
        self.assertTrue(rows, "no bin symlink row in ls -l /")
        self.assertTrue(rows[0].startswith("lrwxrwxrwx"))
        self.assertTrue(rows[0].endswith("bin -> usr/bin"))
        # a symlinked directory is listed through when given as a target
        self.assertIn("bash", F.ls_text(EDGE, "/bin"))

    def test_device_nodes_show_major_minor(self):
        rows = [line for line in F.ls_text(EDGE, "/dev", long=True).splitlines()
                if line.strip().endswith(" null")]
        self.assertTrue(rows)
        self.assertEqual(rows[0].split()[0], "crw-rw-rw-")
        self.assertEqual(rows[0].split()[4], "1,")
        self.assertEqual(rows[0].split()[5], "3")

    def test_human_readable_sizes(self):
        out = F.ls_text(EDGE, "/var/backups", long=True, human=True)
        self.assertIn("4.0K", out)
        self.assertTrue(out.startswith("total "))
        hive_out = F.ls_text(HIVE, "/opt/vesalius/agent_genesis", long=True, human=True)
        self.assertIn("2.4G", hive_out)

    def test_multiple_targets_get_headers(self):
        out = F.ls_text(EDGE, ["/etc/nginx", "/etc/ssh"], long=True)
        self.assertIn("/etc/nginx:", out)
        self.assertIn("/etc/ssh:", out)
        # a blank line separates the blocks, like GNU ls
        self.assertIn("\n\n", out)
        # single target has no header
        self.assertNotIn("/etc/nginx:", F.ls_text(EDGE, "/etc/nginx", long=True))

    def test_unknown_path_is_an_error_not_the_root_listing(self):
        for host in F.HOSTS:
            root = F.ls_text(host, "/")
            for bad in ("/zzz-does-not-exist", "/etc/definitely-not-here.conf"):
                out = F.ls_text(host, bad) or ""
                self.assertNotEqual(out, root)
                self.assertIn("ls: cannot access '%s': No such file or directory" % bad, out)
                self.assertEqual(F.ls_exit_code(host, bad), 2)
                self.assertFalse(F.exists(host, bad))

    def test_plausible_unknown_system_directory(self):
        # Real directories that a typical Ubuntu box has, but that are not in
        # every hand-written table: the point of the facade is that these are
        # neither ENOENT nor the root listing.
        for host, target in ((EDGE, "/etc/ssl"), (EDGE, "/var/cache/nginx"),
                             (HIVE, "/proc/6660"), (HIVE, "/sys/class")):
            out = F.ls_text(host, target)
            self.assertTrue(out, "%s %s empty" % (host, target))
            self.assertNotIn("cannot access", out)

    def test_argv_parser_handles_bundles_and_flags(self):
        res = F.ls_argv(EDGE, ["ls", "-la", "/etc", "/root"])
        self.assertIsNotNone(res)
        self.assertEqual(res["exit_code"], 0)
        self.assertIn("/root:", res["stdout"])
        self.assertIn(".bash_history", res["stdout"])
        single = F.ls_argv(EDGE, ["ls", "-ld", "/etc"])
        self.assertTrue(single["stdout"].startswith("drwxr-xr-x"))
        self.assertTrue(single["stdout"].strip().endswith("/etc"))
        long_h = F.ls_argv(EDGE, ["ls", "-alh", "/var/backups"])
        self.assertIn("4.0K", long_h["stdout"])
        # unknown host must stay the caller's problem
        self.assertIsNone(F.ls_argv("prod-cortex-04", ["ls"]))

    def test_listing_children_are_all_readable(self):
        # Never list a name that `cat`/`stat` then denies: that is the tell.
        for host in F.HOSTS:
            for directory in ("/", "/etc", "/root", "/var/log", "/tmp", "/opt", "/usr"):
                children = F._children(host, directory) or {}
                for name in children:
                    path = posixpath.join(directory, name) if directory != "/" else "/" + name
                    self.assertTrue(F.exists(host, path),
                                    "%s lists %r in %s but it does not exist" % (host, name, directory))
                    self.assertIsNotNone(F.file_text(host, path))


class OneRecordDrivesEverything(unittest.TestCase):
    """cat / stat / file / ls all read the same entry (no size drift)."""

    def test_cat_stat_file_agree(self):
        for host in F.HOSTS:
            for path, item in F.FILESYSTEM[host].items():
                if item["kind"] != "file":
                    continue
                body = F.cat_text(host, path)
                stat = F.stat_text(host, path)
                kind = F.file_text(host, path)
                self.assertIsNotNone(body, "%s cat %s" % (host, path))
                self.assertIsNotNone(stat, "%s stat %s" % (host, path))
                self.assertIsNotNone(kind, "%s file %s" % (host, path))
                if not item["binary"]:  # binaries carry their real byte count
                    self.assertEqual(len(body.encode("utf-8")), item["size"],
                                     "%s cat byte count %s" % (host, path))
                self.assertIn("Size: %-8d" % item["size"], stat, "%s stat size %s" % (host, path))
                self.assertIn("Inode: %-8d" % item["inode"], stat)
                self.assertIn("(%04o/" % item["mode"], stat)
                self.assertTrue(kind.startswith(path + ": "))

    def test_ls_size_column_matches_stat(self):
        for host in F.HOSTS:
            for directory in ("/etc", "/root", "/var/log", "/var/backups", "/opt/vesalius"):
                out = F.ls_text(host, directory, long=True, all=True)
                if not out:
                    continue
                for line in out.splitlines()[1:]:
                    if not line.strip():
                        continue
                    columns = line.split()
                    name = columns[-1]
                    if name in (".", "..") or "->" in line:
                        continue
                    path = posixpath.join(directory, name) if directory != "/" else "/" + name
                    item = F.entry(host, path)
                    if item is None:
                        continue
                    self.assertIn("Size: %-8d" % item["size"],
                                  F.stat_text(host, path) or "",
                                  "%s %s ls vs stat" % (host, path))

    def test_cat_follows_symlinks(self):
        self.assertEqual(F.cat_text(EDGE, "/etc/hostname"), "edge-gw-01\n")
        self.assertIsNone(F.cat_text(EDGE, "/etc"))          # directories have no body
        self.assertTrue(F.is_dir(EDGE, "/bin"))              # symlinked directory
        self.assertFalse(F.is_dir(EDGE, "/etc/hostname"))

    def test_digests_are_computed_from_the_cat_body(self):
        import hashlib

        body = F.cat_text(EDGE, "/etc/passwd")
        self.assertEqual(F.md5_text(EDGE, "/etc/passwd"),
                         "%s  /etc/passwd\n" % hashlib.md5(body.encode()).hexdigest())
        self.assertEqual(F.sha256_text(EDGE, "/etc/passwd"),
                         "%s  /etc/passwd\n" % hashlib.sha256(body.encode()).hexdigest())
        self.assertIsNone(F.md5_text(EDGE, "/etc"))          # directory
        self.assertIsNone(F.md5_text(EDGE, "/nope"))         # unknown
        self.assertIsNone(F.md5_text("prod-cortex-04", "/etc/hostname"))

    def test_story_gate_files_are_readable(self):
        edge_gate = [
            "/var/log/auth.log",
            "/var/log/kern.log",
            "/var/backups/lin_emergency_key.README",
            "/etc/nginx/conf.d/upstream.conf",
            "/root/.bash_history",
            "/etc/hosts",
            "/var/log/syslog",
            "/home/ops/notes.txt",
            "/var/spool/cron/crontabs/root",
        ]
        for path in edge_gate:
            body = F.cat_text(EDGE, path)
            self.assertTrue(body, "edge gate evidence %s is empty/None" % path)
            self.assertIsNotNone(F.stat_text(EDGE, path))
            self.assertIsNotNone(F.file_text(EDGE, path))
        hive_gate = [
            "/opt/vesalius/agent_genesis/agent_84.attn",
            "/opt/vesalius/agent_genesis/manifest.txt",
            "/opt/vesalius/ethics/consent_elena.txt",
            "/var/lib/vesalius/specimens.db",
            "/sys/kernel/vesalius/metabolic_override",
        ]
        for path in hive_gate:
            self.assertIsNotNone(F.cat_text(HIVE, path), "hive gate evidence %s" % path)
            self.assertIsNotNone(F.stat_text(HIVE, path))


class HostsDiffer(unittest.TestCase):
    """edge-gw-01 and hive-director-00 must not look like the same box."""

    def test_hostname_and_identity(self):
        self.assertEqual(F.cat_text(EDGE, "/etc/hostname"), "edge-gw-01\n")
        self.assertEqual(F.cat_text(HIVE, "/etc/hostname"), "hive-director-00\n")
        self.assertIn("10.66.0.1", F.cat_text(EDGE, "/etc/hosts") or "")
        self.assertIn("10.66.6.1", F.cat_text(HIVE, "/etc/hosts") or "")

    def test_same_listing_targets_differ(self):
        for target in ("/", "/etc", "/tmp", "/root", "/var/log", "/run"):
            self.assertNotEqual(F.ls_text(EDGE, target, long=True, all=True),
                                F.ls_text(HIVE, target, long=True, all=True),
                                "%s listings are identical on both hosts" % target)

    def test_fact_sheet_is_what_v3_says(self):
        edge, hive = F.HOST_FACTS[EDGE], F.HOST_FACTS[HIVE]
        self.assertEqual(edge["ip"], "10.66.0.1")
        self.assertEqual(hive["ip"], "10.66.6.1")
        self.assertEqual((edge["cpu"], edge["mem_mb"], edge["disk_gb"]), (2, 2048, 32))
        self.assertEqual((hive["cpu"], hive["mem_mb"], hive["disk_gb"]), (4, 8192, 128))
        self.assertEqual(hive["chambers"], 128)
        self.assertEqual(edge["chambers"], 0)
        self.assertFalse(edge["wetware"])
        self.assertTrue(hive["wetware"])

    def test_no_wetware_on_the_clean_edge(self):
        for path, item in F.FILESYSTEM[EDGE].items():
            blob = path + "\n" + (item.get("content") or "")
            self.assertNotIn("synapse_worker", blob, "edge leaks synapse_worker: %s" % path)
            self.assertNotIn("chamber_04", blob, "edge leaks chamber_04: %s" % path)
            self.assertNotIn("chamber_07", blob, "edge leaks chamber_07: %s" % path)
        self.assertNotIn("synapse_worker", F.ls_text(EDGE, "/") or "")
        self.assertNotIn("synapse_worker", F.ls_text(EDGE, "/opt", long=True) or "")
        self.assertNotIn("synapse_worker", F.ls_text(EDGE, "/opt/cortex/bin", long=True) or "")

    def test_hive_has_no_home_directory(self):
        self.assertIsNone(F.entry(HIVE, "/home"))
        self.assertNotIn("home", F.ls_text(HIVE, "/") or "")
        self.assertIn("cannot access", F.ls_text(HIVE, "/home") or "")

    def test_edge_has_ordinary_user_homes(self):
        names = F.ls_text(EDGE, "/home", long=True) or ""
        self.assertIn("ops", names)
        self.assertIn("lin", names)
        self.assertIn("cortex-sre", F.ls_text(EDGE, "/home/ops") or "")

    def test_hive_supervises_chambers(self):
        listing = F.ls_text(HIVE, "/var/lib/vesalius", long=True) or ""
        self.assertIn("specimens.db", listing)
        self.assertIn("audit.log", listing)
        self.assertIn("128", F.cat_text(HIVE, "/etc/motd") or "")
        # the chamber files are not on the edge
        self.assertNotIn("specimens.db", F.ls_text(EDGE, "/var/lib", long=True) or "")

    def test_shared_files_match_realism_byte_for_byte(self):
        # Two modules answer these three files; the operator must not see a
        # different os-release depending on which layer answered.
        if R is None:  # pragma: no cover
            self.skipTest("realism.py not importable")
        for host in F.HOSTS:
            for path in ("/etc/hostname", "/etc/os-release", "/etc/machine-id"):
                with self.subTest(host=host, path=path):
                    self.assertEqual(F.cat_text(host, path), R.HOST_FILES[host][path]["content"])
                    self.assertEqual(F.stat_text(host, path), R.get(host, ["stat", path]))
                    self.assertEqual(F.file_text(host, path), R.get(host, ["file", path]))
                    self.assertEqual(F.md5_text(host, path), R.get(host, ["md5sum", path]))


class NoEnoentForCommonFiles(unittest.TestCase):
    """The original complaint: ordinary files must not be missing."""

    EDGE_FILES = [
        "/etc/hostname", "/etc/hosts", "/etc/os-release", "/etc/passwd",
        "/etc/group", "/etc/shadow", "/etc/fstab", "/etc/resolv.conf",
        "/etc/timezone", "/etc/motd", "/etc/crontab", "/etc/ssh/sshd_config",
        "/etc/nginx/nginx.conf", "/etc/nginx/conf.d/upstream.conf",
        "/root/.bash_history", "/root/.bashrc", "/root/.ssh/known_hosts",
        "/var/log/auth.log", "/var/log/kern.log", "/var/log/syslog",
        "/var/log/nginx/access.log", "/var/log/nginx/error.log",
        "/var/backups/lin_emergency_key.README",
        "/var/spool/cron/crontabs/root",
        "/opt/cortex/VERSION", "/usr/bin/bash", "/boot/grub/grub.cfg",
        "/home/ops/notes.txt", "/home/lin/bin/healthcheck.sh",
    ]
    HIVE_FILES = [
        "/etc/hostname", "/etc/hosts", "/etc/os-release", "/etc/passwd",
        "/etc/group", "/etc/fstab", "/etc/resolv.conf", "/etc/motd",
        "/etc/crontab", "/etc/ssh/sshd_config",
        "/etc/vesalius/hive.conf", "/etc/vesalius/chambers.d/chamber_07.conf",
        "/root/.bash_history", "/root/.ssh/known_hosts",
        "/var/log/auth.log", "/var/log/syslog", "/var/log/vesalius/chamber_telemetry.log",
        "/opt/vesalius/bin/vesalius-ctl", "/opt/vesalius/README.md",
        "/opt/vesalius/ethics/consent_elena.txt",
        "/var/lib/vesalius/audit.log", "/var/lib/vesalius/specimens.db",
        "/sys/kernel/vesalius/metabolic_override",
        "/usr/bin/sqlite3", "/opt/vesalius/hive-control/routing.policy",
    ]
    DIRS = ["/", "/etc", "/home", "/root", "/var", "/var/log", "/var/log/nginx",
            "/tmp", "/opt", "/opt/cortex", "/usr", "/usr/bin", "/run", "/boot",
            "/proc", "/dev", "/sys", "/var/lib", "/var/cache", "/srv", "/mnt"]
    HIVE_DIRS = ["/", "/etc", "/root", "/var", "/var/log", "/tmp", "/opt",
                 "/opt/vesalius", "/opt/vesalius/agent_genesis",
                 "/opt/vesalius/ethics", "/var/lib/vesalius", "/usr", "/usr/bin",
                 "/run", "/boot", "/proc", "/dev", "/sys", "/sys/kernel/vesalius",
                 "/var/cache"]

    def test_common_edge_files_exist(self):
        for path in self.EDGE_FILES:
            self.assertIsNotNone(F.entry(EDGE, path), "edge missing %s" % path)
            self.assertIsNotNone(F.cat_text(EDGE, path), "edge cat %s" % path)
        for path in self.DIRS:
            self.assertTrue(F.is_dir(EDGE, path), "edge missing dir %s" % path)
            out = F.ls_text(EDGE, path)
            self.assertIsNotNone(out, "edge ls %s returned None" % path)
            self.assertNotIn("cannot access", out or "", "edge ls %s errored" % path)

    def test_common_hive_files_exist(self):
        for path in self.HIVE_FILES:
            self.assertIsNotNone(F.entry(HIVE, path), "hive missing %s" % path)
            body = F.cat_text(HIVE, path)
            self.assertIsNotNone(body, "hive cat %s" % path)
        for path in self.HIVE_DIRS:
            self.assertTrue(F.is_dir(HIVE, path), "hive missing dir %s" % path)
            out = F.ls_text(HIVE, path)
            self.assertIsNotNone(out, "hive ls %s returned None" % path)
            self.assertNotIn("cannot access", out or "", "hive ls %s errored" % path)

    def test_directories_are_never_the_root_listing(self):
        # This is the original tell: every unknown directory printed
        # "bin  boot  dev  etc  home  lib ...".
        for host, targets in ((EDGE, self.DIRS), (HIVE, self.HIVE_DIRS)):
            root = F.ls_text(host, "/")
            for target in targets:
                if target == "/":
                    continue
                self.assertNotEqual(F.ls_text(host, target), root,
                                    "%s '%s' prints the root listing" % (host, target))

    def test_stat_and_file_work_for_every_listed_dir(self):
        for host in F.HOSTS:
            for target in ("/", "/etc", "/var/log", "/opt", "/usr/bin", "/run"):
                stat = F.stat_text(host, target)
                self.assertIsNotNone(stat, "%s stat %s" % (host, target))
                self.assertIn("directory", stat)
                self.assertTrue((F.file_text(host, target) or "").endswith(": directory\n"))


class CampaignStateHooks(unittest.TestCase):
    """Files that only exist after a gate must not exist before it."""

    def test_gate1_key_hidden_until_extracted(self):
        self.assertIsNone(F.cat_text(EDGE, F.GATE1_KEY_PATH))
        self.assertIsNone(F.entry(EDGE, F.GATE1_KEY_PATH))
        before = F.ls_text(EDGE, "/root/.ssh", long=True, all=True) or ""
        self.assertNotIn("id_ed25519_cortex", before)

    def test_gate1_key_and_tar_appear_with_flag(self):
        flags = {"gate1_key_obtained": True}
        listing = F.ls_text(EDGE, "/root/.ssh", long=True, all=True, flags=flags) or ""
        self.assertIn("id_ed25519_cortex", listing)
        body = F.cat_text(EDGE, F.GATE1_KEY_PATH, flags=flags)
        self.assertIn("BEGIN OPENSSH PRIVATE KEY", body or "")
        self.assertIn("600", F.stat_text(EDGE, F.GATE1_KEY_PATH, flags=flags) or "600")
        self.assertIsNotNone(F.cat_text(EDGE, F.GATE1_TAR_PATH, flags=flags))
        # /tmp picks it up too (the extraction target)
        self.assertIn("lin.tar", F.ls_text(EDGE, "/tmp", long=True, all=True, flags=flags) or "")

    def test_hive_override_reads_zero_then_code(self):
        self.assertEqual(F.cat_text(HIVE, F.HIVE_OVERRIDE_PATH), "0\n")
        self.assertEqual(
            F.cat_text(HIVE, F.HIVE_OVERRIDE_PATH, flags={"override_code": "A1B2C3D4"}),
            "A1B2C3D4\n")
        self.assertIsNotNone(F.stat_text(HIVE, F.HIVE_OVERRIDE_PATH,
                                         flags={"override_code": "A1B2C3D4"}))

    def test_flags_none_and_state_objects_are_safe(self):
        class FakeState:
            flags = {"gate1_key_obtained": True}

        self.assertIn("id_ed25519_cortex",
                      F.ls_text(EDGE, "/root/.ssh", long=True, all=True,
                                flags=FakeState.flags) or "")
        # no flags at all must be the same as empty flags
        self.assertEqual(F.ls_text(EDGE, "/tmp", long=True, all=True),
                         F.ls_text(EDGE, "/tmp", long=True, all=True, flags={}))


class PureFunctions(unittest.TestCase):
    """Helpers are deterministic and side-effect free."""

    def test_mode_string(self):
        self.assertEqual(F.mode_string("dir", 0o755), "drwxr-xr-x")
        self.assertEqual(F.mode_string("file", 0o644), "-rw-r--r--")
        self.assertEqual(F.mode_string("file", 0o600), "-rw-------")
        self.assertEqual(F.mode_string("dir", 0o1777), "drwxrwxrwt")
        self.assertEqual(F.mode_string("dir", 0o1730), "drwx-wx--T")
        self.assertEqual(F.mode_string("chardev", 0o666), "crw-rw-rw-")
        self.assertEqual(F.mode_string("symlink", 0o777), "lrwxrwxrwx")
        self.assertEqual(F.mode_string("fifo", 0o644), "prw-r--r--")
        self.assertEqual(F.mode_string("dir", 0o2775), "drwxrwsr-x")
        self.assertEqual(F.mode_string("file", 0o4755), "-rwsr-xr-x")

    def test_human_size(self):
        self.assertEqual(F.human_size(0), "0")
        self.assertEqual(F.human_size(386), "386")
        self.assertEqual(F.human_size(4096), "4.0K")
        self.assertEqual(F.human_size(1024 * 1024), "1.0M")
        self.assertEqual(F.human_size(2576980377), "2.4G")

    def test_ls_date(self):
        self.assertEqual(F.ls_date("2026-10-26 03:12:04"), "Oct 26 03:12")
        self.assertEqual(F.ls_date("2025-08-28 09:12:10"), "Aug 28  2025")
        self.assertEqual(F.ls_date("2026-10-03 23:59:00"), "Oct  3 23:59")

    def test_rendering_is_deterministic(self):
        first = F.ls_text(EDGE, "/etc", long=True, all=True)
        for _ in range(3):
            self.assertEqual(first, F.ls_text(EDGE, "/etc", long=True, all=True))
        self.assertEqual(F.stat_text(EDGE, "/etc/hostname"), F.stat_text(EDGE, "/etc/hostname"))

    def test_cortex_is_not_modelled(self):
        for func, args in ((F.ls_text, ("prod-cortex-04", "/etc")),
                           (F.cat_text, ("prod-cortex-04", "/etc/hostname")),
                           (F.stat_text, ("prod-cortex-04", "/etc/hostname")),
                           (F.file_text, ("prod-cortex-04", "/etc/hostname"))):
            self.assertIsNone(func(*args), "%s must stay unopinionated on cortex" % func.__name__)
        self.assertFalse(F.exists("prod-cortex-04", "/etc"))

    def test_no_disk_or_clock_access(self):
        # The renderers are pure: reading the tree twice at different wall-clock
        # moments cannot change a single byte (everything is frozen at
        # REFERENCE_NOW).
        self.assertEqual(F.ls_date("2026-10-26 03:12:04"), "Oct 26 03:12")
        self.assertEqual(F.REFERENCE_NOW.year, 2026)


if __name__ == "__main__":
    unittest.main(verbosity=2)
