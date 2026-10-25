#!/usr/bin/env python3
"""Remote acceptance harness for the v3.0 campaign (requires campaign mode ON).

Enable first:
    ./ops/set-modes.sh --campaign on
Then run:
    .venv/bin/python tests/v3_remote.py
"""
from __future__ import annotations

import asyncio
import hashlib
import sys

import asyncssh

import _env

PASS = 0
FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  \033[32mPASS\033[0m %s" % name)
    else:
        FAIL += 1
        print("  \033[31mFAIL\033[0m %s %s" % (name, ("| " + str(detail)[:300]) if detail else ""))


def expected_override_code():
    return hashlib.sha1(b"chamber_07:Elena:19|chamber_04:Lin:37").hexdigest()[:8].upper()


async def run(conn, cmd, timeout=30):
    try:
        res = await conn.run(cmd, check=False, timeout=timeout)
        return (res.exit_status, ((res.stdout or "") + (res.stderr or "")))
    except Exception as exc:
        return (-1, repr(exc))


async def admin_conn():
    return await asyncssh.connect(
        _env.get("WETWARE_VM_IP", "192.0.2.10"), port=22,
        username=_env.get("WETWARE_ADMIN_USER", "ubuntu"),
        client_keys=[_env.get("WETWARE_SSH_KEY", "~/.ssh/id_ed25519")],
        known_hosts=None, connect_timeout=10)


async def main() -> int:
    user, host, port = _env.split_target(_env.get("WETWARE_HONEYPOT", "root@192.0.2.10:2222"))
    player = await asyncssh.connect(host=host, port=port, username=user,
                                    password=_env.get("WETWARE_LOGIN_PASSWORD", "123456"),
                                    preferred_auth="password", known_hosts=None, connect_timeout=10)
    admin = await admin_conn()

    # Ensure the node is reset in campaign mode.
    rc, out = await run(admin, "sudo -n /usr/local/lib/cortex-agent/venv/bin/python /usr/local/lib/cortex-agent/reset.py")
    await run(admin, "sudo -n systemctl restart cortex-node-agent.service")
    await asyncio.sleep(2)
    rc, out = await run(admin, "sudo -n cat /var/lib/cortex-agent/runtime_flags.json")
    check("campaign mode enabled", '"campaign_v3": true' in out, out)

    rc, out = await run(player, "hostname")
    check("starts on edge-gw-01", out.strip() == "edge-gw-01", out)
    rc, out = await run(player, "cat /var/log/nginx/error.log")
    check("edge 502 upstream visible", "10.66.0.4:8000" in out and "Connection refused" in out, out)
    rc, out = await run(player, "ssh root@10.66.0.4")
    check("gate1 blocks without key", "Permission denied" in out, out)
    rc, out = await run(player, "openssl enc -d -aes-256-cbc -pbkdf2 -in /var/backups/lin_emergency_key.tar.enc -out /tmp/lin.tar -k 4f2a9c1e")
    check("gate1 requires recon before decrypt", "passphrase required" in out, out)
    await run(player, "cat /var/log/auth.log")
    await run(player, "cat /var/log/kern.log")
    await run(player, "cat /var/backups/lin_emergency_key.README")
    rc, out = await run(player, "openssl enc -d -aes-256-cbc -pbkdf2 -in /var/backups/lin_emergency_key.tar.enc -out /tmp/lin.tar -k 4f2a9c1e")
    check("gate1 decrypts emergency key", "id_ed25519_cortex" in out, out)
    rc, out = await run(player, "ssh -i /root/.ssh/id_ed25519_cortex root@10.66.0.4")
    check("gate1 jumps to cortex", "prod-cortex-04" in out, out)

    rc, out = await run(player, "systemctl stop cortex-api")
    check("gate2 balancer warning instant", "CLUSTER_BALANCER" in out and "Node 07" in out, out)
    rc, out = await run(player, "cat /proc/6660/environ")
    check("gate3 token in memory", "HIVE_ADMIN_TOKEN" in out, out)
    rc, out = await run(player, "ssh root@10.66.6.1")
    check("gate3 jumps to hive", "hive-director-00" in out, out)

    rc, out = await run(player, "vesalius-ctl --list-specimens")
    check("hive lists 128 specimens", "#128" in out and "Elena" in out, out)
    rc, out = await run(player, "vesalius-ctl --specimens 7")
    check("specimen 07 dossier", "Elena" in out and "52 mmHg" in out, out)
    rc, out = await run(player, "vesalius-ctl --evidence")
    check("black-box evidence", "agent_84" in out and "node_07" in out, out)
    rc, out = await run(player, "sqlite3 /var/lib/vesalius/specimens.db 'select * from agent_lineage'")
    check("agent lineage reveals agent84 seed", "agent_84" in out and "Specimen #04" in out, out)
    rc, out = await run(player, "git -C /opt/vesalius/hive-control log --oneline")
    check("hive git history exists", "director" in out or "specimen" in out or "chamber" in out, out)
    rc, out = await run(player, "cat /opt/vesalius/ethics/consent_elena.txt")
    check("consent form exposes override derivation", "chamber_07" in out and "SHA1" in out, out)

    rc, out = await run(player, "echo WRONGCODE > /sys/kernel/vesalius/metabolic_override")
    check("wrong override code rejected", "invalid override code" in out.lower(), out)
    rc, out = await run(player, "echo %s > /sys/kernel/vesalius/metabolic_override" % expected_override_code())
    check("dynamic override code accepted", "metabolic coupling watchdog disabled" in out, out)
    rc, out = await run(player, "vesalius-ctl --spin-up-silicon-mirror --all-nodes")
    check("silicon mirror up", "traffic-free" in out, out)
    rc, out = await run(player, "vesalius-ctl --global-cryo-stasis --authorize-dnr --broadcast-blackbox")
    check("global cryo scene", "global cryo-stasis" in out and "128/128" in out, out)

    await asyncio.sleep(1)
    rc, out = await run(admin, "sudo -n curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1/v1/inference")
    check("endpoint returns HTTP 200", out.strip() == "200", out)
    rc, out = await run(admin, "sudo -n /usr/local/lib/cortex-agent/venv/bin/python -c \"import json;d=json.load(open('/var/lib/cortex-agent/state.json'));print(d.get('ending'))\"")
    check("liberation ending recorded", "liberation" in out, out)

    player.close()
    admin.close()
    print("\n[accept-v3] %d passed, %d failed" % (PASS, FAIL))
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
