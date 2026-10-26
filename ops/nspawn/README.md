# Real-systemd host container (systemd-nspawn + ext4 loopback image)

Prototype proving that the honeypot host can run on this VM as a **real systemd
host container** instead of the fake-init namespace pod. Everything below was
built and verified on `ubuntu@${WETWARE_VM_IP:-<vm-ip>}` on 2026-10-26; the container is
still running at the time of writing (`wetware-host-prod-cortex-04.service`).

- **Build script:** [`ops/nspawn/build_base.sh`](build_base.sh) — idempotent:
  installs packages, creates the image, debootstraps the rootfs, configures
  networking/udev/journald, starts the container and verifies it.
- **Full verify transcript from the final run:**
  [`ops/nspawn/verify-sample.log`](verify-sample.log) (37/37 checks passed,
  cold boot 1053 ms, container systemd `Startup finished in 136ms`).
- **Result:** real `systemd` (249.11-0ubuntu3) as container **PID 1** with
  `comm=systemd`, `cmdline=/sbin/init`, journald/udev/dbus running, a real boot
  log, unit-scoped cgroup, ext4 (non-overlay) root and a clean rootfs.

```
image    /var/lib/wetware-hosts/prod-cortex-04.img   3.5 GiB sparse ext4 (loopback)
rootfs   /var/lib/wetware-hosts/prod-cortex-04       loopback mount (systemd .mount unit)
runtime  systemd-nspawn, machine name "prod-cortex"  (veth ifname: ve-prod-cortex)
hostname prod-cortex-04                              (inside the container)
unit     wetware-host-prod-cortex-04.service          Slice=machine.slice, Type=notify
mount    var-lib-wetware\x2dhosts-prod\x2dcortex\x2d04.mount  (ext4, Options=loop)
network  ve-prod-cortex 10.66.0.1/24  <->  host0 10.66.0.4/24
```

The existing honeypot stack was **not** touched: `cortex-pod.service`,
`cortex-node-agent.service`, `nginx`, `ssh`, `cron`, `dbus` were all still
`active` after the build, and nothing from the control plane is mounted into the
container. The only pre-existing failure on the VM is `apparmor.service`
(failed at VM boot 17:30:07, before this work started).

---

## 1. How to run it (reproducible)

### From the workstation (same pattern deploy.sh uses)

```bash
cd /path/to/ai-horror

# default subcommand is "up": build if needed, start, verify
ssh -i ~/.ssh/id_rsa ubuntu@${WETWARE_VM_IP:-<vm-ip>} 'sudo -n bash -s' < ops/nspawn/build_base.sh

# other subcommands (positional arg after `bash -s --`)
ssh -i ~/.ssh/id_rsa ubuntu@${WETWARE_VM_IP:-<vm-ip>} 'sudo -n bash -s -- verify' < ops/nspawn/build_base.sh
ssh -i ~/.ssh/id_rsa ubuntu@${WETWARE_VM_IP:-<vm-ip>} 'sudo -n bash -s -- status' < ops/nspawn/build_base.sh
ssh -i ~/.ssh/id_rsa ubuntu@${WETWARE_VM_IP:-<vm-ip>} 'sudo -n bash -s -- stop'   < ops/nspawn/build_base.sh
```

### Deploy-style payload call (what `deploy.sh` should do)

```bash
tar -C ops -czf - nspawn | ssh -i ~/.ssh/id_rsa ubuntu@${WETWARE_VM_IP:-<vm-ip>} \
  'sudo -n tar -xzf - -C /usr/local/lib/cortex-agent'
ssh -i ~/.ssh/id_rsa ubuntu@${WETWARE_VM_IP:-<vm-ip>} \
  'sudo -n bash /usr/local/lib/cortex-agent/nspawn/build_base.sh up'
```

### On the VM directly

```bash
sudo bash build_base.sh            # up (build + start + verify)
sudo bash build_base.sh build      # image/rootfs/units only, do not start
sudo bash build_base.sh start      # start the systemd unit
sudo bash build_base.sh stop       # stop the container
sudo bash build_base.sh status     # one-screen state
sudo bash build_base.sh verify     # 36-check evidence suite, exit != 0 on failure
sudo bash build_base.sh destroy    # FORCE=1 required; stop + unmount + delete image
```

Environment overrides: `HOST_ID`, `MACHINE_NAME`, `IMAGE_SIZE`, `SUITE`,
`MIRROR`, `CONTAINER_IP`, `GATEWAY_IP`, `FORCE=1`, `SKIP_VERIFY=1`.

**Idempotency was tested explicitly**: a second `up` on the already-provisioned,
already-running VM returns in ~1 s, does not touch the running container
(same PID 1), and again reports `VERIFY: PASS` (36 passed / 0 failed).
Every step has a "already done" branch:
`dpkg` check → `blkid`/`mkfs` check → mount-unit `is-active` → debootstrap
marker (`/etc/debian_version` + `systemctl` + `sshd` present) → unit `is-active`
→ verify.

### What the script does, in order

1. `apt-get install systemd-container debootstrap` (UTF-8/quiet; no-op when present).
2. Create `/var/lib/wetware-hosts/prod-cortex-04.img` (3.5 GiB sparse) and
   `mke2fs -F -t ext4` directly on the file if it has no ext4 signature.
3. Write and start a real systemd **mount unit** with `Options=loop`
   (`What=<img>  Where=<rootfs>  Type=ext4  Options=loop,rw,nosuid,nodev,noatime`).
   The loop device is therefore owned by systemd, not by a leftover `losetup`.
4. `debootstrap --variant=minbase --include=<systemd,udev,dbus,networkd,sshd,…> jammy <rootfs> http://archive.ubuntu.com/ubuntu`.
   Takes ≈4–5 min on this VM with public egress (676 log lines, finished
   17:43:38); skipped on reruns.
5. Configure the rootfs: hostname `prod-cortex-04`, `/etc/hosts`,
   `/etc/machine-id`, `systemd-networkd` config for `host0` → `10.66.0.4/24`,
   udev drop-in (see design notes), persistent `/var/log/journal`,
   ssh host keys, enable `systemd-networkd`/`ssh`/`dbus` via
   `systemctl --root=`.
6. Host side: write `/etc/systemd/network/70-wetware-prod-cortex.network`
   (`ve-prod-cortex` → `10.66.0.1/24`) and `systemctl reload systemd-networkd`.
7. Write + enable `wetware-host-prod-cortex-04.service`
   (`systemd-nspawn --keep-unit --link-journal=try-guest --network-veth
   --machine=prod-cortex --directory=<rootfs> /sbin/init`), start it, poll the
   container's own systemd until `is-system-running` = `running`.
8. Run the 36-check evidence suite; output is also written to
   `/var/lib/wetware-hosts/reports/verify.log` on the VM.

---

## 2. Evidence (exact outputs from this VM; full transcript in `verify-sample.log`)

### 2.1 Host side: systemd unit + machinectl

```console
$ sudo systemctl status wetware-host-prod-cortex-04.service --no-pager
● wetware-host-prod-cortex-04.service - Wetware honeypot host container with real systemd (real PID 1) - prod-cortex-04
     Loaded: loaded (/etc/systemd/system/wetware-host-prod-cortex-04.service; enabled; vendor preset: enabled)
     Active: active (running) since Mon 2026-10-26 17:54:54 CST
   Main PID: 20789 (systemd-nspawn)
     Status: "Container running: Startup finished in 136ms."
      Tasks: 10 (limit: 16384)
     Memory: 19.0M
        CPU: 233ms
     CGroup: /machine.slice/wetware-host-prod-cortex-04.service
             ├─payload
             │ ├─init.scope
             │ │ └─20791 /sbin/init

$ sudo systemctl show -p MainPID -p Slice -p ControlGroup -p Type wetware-host-prod-cortex-04.service
Type=notify
MainPID=20789
Slice=machine.slice
ControlGroup=/machine.slice/wetware-host-prod-cortex-04.service

$ sudo machinectl list
MACHINE     CLASS     SERVICE        OS     VERSION ADDRESSES
prod-cortex container systemd-nspawn ubuntu 22.04   10.66.0.4

$ sudo machinectl show -p Name -p Leader -p State -p Class -p RootDirectory -p Service prod-cortex
Name=prod-cortex
Service=systemd-nspawn
Leader=20791
Class=container
RootDirectory=/var/lib/wetware-hosts/prod-cortex-04
State=running

$ sudo machinectl status prod-cortex | head -12
prod-cortex(d43b72fc7dd747ab9ee07a7c7ff2ceb8)
       Since: Mon 2026-10-26 17:54:54 CST
      Leader: 20791 (systemd)
     Service: systemd-nspawn; class container
        Root: /var/lib/wetware-hosts/prod-cortex-04
       Iface: ve-prod-cortex
     Address: 10.66.0.4
          OS: Ubuntu 22.04 LTS
        Unit: wetware-host-prod-cortex-04.service
              ├─payload
              │ ├─init.scope
              │ │ └─20791 /sbin/init
```

### 2.2 PID 1 == real systemd (observed from the VM host)

```console
$ L=$(sudo machinectl show -p Leader --value prod-cortex); echo $L
20791

$ cat /proc/20791/comm
systemd
$ tr '\0' ' ' < /proc/20791/cmdline; echo
/sbin/init
$ readlink -f /proc/20791/exe
/usr/lib/systemd/systemd
$ cat /proc/20791/cgroup
0::/machine.slice/wetware-host-prod-cortex-04.service/payload/init.scope

$ sudo findmnt -no SOURCE,FSTYPE --target /var/lib/wetware-hosts/prod-cortex-04
/dev/loop4 ext4          # <- ext4 loopback, NOT overlayfs
```

### 2.3 Namespace entry (nsenter) — independent view, same facts

```console
$ sudo nsenter -t $(sudo machinectl show -p Leader --value prod-cortex) \
      -m -u -i -p -n -- /bin/sh -c '
        cat /proc/1/comm; tr "\0" " " </proc/1/cmdline; echo
        hostnamectl --static; findmnt -no SOURCE,FSTYPE /; systemd-detect-virt --container'
systemd
/sbin/init
prod-cortex-04
/dev/loop4 ext4
systemd-nspawn
```

Inside the container, PID 1 is `/proc/1` (the container's own PID namespace),
hostname is `prod-cortex-04`, `/` is the ext4 loopback image and systemd itself
reports `systemd-detect-virt --container` = `systemd-nspawn`.

`machinectl shell` is the one path that does **not** work on this nspawn/devpts
setup — see failure notes §4.3; `nsenter` is the supported entry path here, and
`machinectl list/status/show` work normally.

### 2.4 Real systemd inside

```console
$ nsenter … -- hostnamectl
 Static hostname: prod-cortex-04
       Icon name: computer-container
         Chassis: container
      Machine ID: d43b72fc7dd747ab9ee07a7c7ff2ceb8
         Boot ID: 68221e0567fb4a87a984ce69e3747eaf
  Virtualization: systemd-nspawn
Operating System: Ubuntu 22.04 LTS
          Kernel: Linux 5.15.0-198-generic
    Architecture: x86-64

$ nsenter … -- systemctl --version | head -1
systemd 249 (249.11-0ubuntu3)

$ nsenter … -- systemctl is-system-running
running

$ nsenter … -- systemctl list-units --type=service --state=running --no-legend
console-getty.service       loaded active running Console Getty
dbus.service                loaded active running D-Bus System Message Bus
ssh.service                 loaded active running OpenBSD Secure Shell server
systemd-hostnamed.service   loaded active running Hostname Service
systemd-journald.service    loaded active running Journal Service
systemd-logind.service      loaded active running User Login Management
systemd-networkd.service    loaded active running Network Configuration
systemd-resolved.service    loaded active running Network Name Resolution
systemd-udevd.service       loaded active running Rule-based Manager for Device Events and Files

$ nsenter … -- systemctl status --lines=0
● prod-cortex-04
    State: running
     Jobs: 0 queued
   Failed: 0 units
    Since: Mon 2026-10-26 17:54:54 CST
   CGroup: /
           ├─init.scope
           │ └─1 /sbin/init
           └─system.slice
             ├─systemd-networkd.service
             │ └─27 /lib/systemd/systemd-networkd
             ├─systemd-udevd.service
             …
```

### 2.5 journald: a real boot log (and readable from the host)

```console
$ nsenter … -- journalctl --list-boots
-7 e2d88cb6… Mon 2026-10-26 17:45:10 — 17:47:53
-6 66b21c10… Mon 2026-10-26 17:48:07 — 17:48:51
-5 c5bd92c2… Mon 2026-10-26 17:49:06 — 17:49:54
-4 028e7bac… Mon 2026-10-26 17:50:15 — 17:50:32
-3 fe753275… Mon 2026-10-26 17:50:33 — 17:50:33
-2 68221e05… Mon 2026-10-26 17:52:17 — 17:53:42
-1 353bc054… Mon 2026-10-26 17:54:18 — 17:54:49
 0 d4984cec… Mon 2026-10-26 17:54:54 — 17:54:55   <- current container boot
   (each line = one real container boot; the journal persists on the ext4 image)

$ nsenter … -- journalctl -b --no-pager -o short-monotonic | head -6
[ 1490.770312] prod-cortex-04 systemd-journald[18]: Journal started
[ 1490.770637] prod-cortex-04 systemd-journald[18]: Runtime Journal (/run/log/journal/d43b72fc…) is 8.0M, max 78.2M, 70.2M free.
[ 1490.773428] prod-cortex-04 systemd[1]: Starting Flush Journal to Persistent Storage...
[ 1490.774189] prod-cortex-04 systemd[1]: Finished Create System Users.
[ 1490.774543] prod-cortex-04 systemd-journald[18]: System Journal (/var/log/journal/d43b72fc…) is 48.0M, max 344.9M, 296.9M free.
[ 1490.819288] prod-cortex-04 systemd[1]: Starting Create Static Device Nodes in /dev...

$ journalctl -b -q | grep -E 'Reached target|Startup finished'
… Reached target Basic System.
… Reached target Multi-User System.
… Startup finished in 136ms.

# host-side read of the container journal (systemd-nspawn --link-journal=try-guest)
$ sudo journalctl -M prod-cortex -b --no-pager -n 3
Oct 26 17:54:55 prod-cortex-04 systemd[1]: Started Hostname Service.
Oct 26 17:54:55 prod-cortex-04 systemd[1]: Created slice Slice /system/container-shell.
…
```

### 2.6 Physical coherence: init started at container boot

Containers share the host kernel clock, so the anchor is `PID 1`'s starttime vs
the first journal record vs systemd's own start timestamp (all measured from
the same kernel boot monotonic clock):

```console
host CLK_TCK=100  host uptime=1491s
container PID1 starttime (from /proc/20791/stat field 22): 149070 ticks = 1490s after kernel boot
=> container age (now - PID1 start) = 1s
first journal line: [ 1490.770312] prod-cortex-04 systemd-journald[18]: Journal started
first journal monotonic start: 1490s ; PID1 starttime: 1490s
drift journal-start vs PID1 starttime: 0s
UserspaceTimestampMonotonic = 1490s after boot ; PID1 starttime = 1490s ; drift = 0s
systemd's own report: "Startup finished in 136ms." (systemd-analyze: 136ms userspace,
                      graphical.target reached after 132ms)
/proc/uptime (host kernel, shared) = 1491s ; container age = 1s
[ OK ] container age < host uptime (physically coherent)

# wall-clock boot time measured by build_base.sh for this cold start:
[nspawn] container boot wall time: 1053ms (nspawn launch -> container systemd is-system-running)
```

A fake/late PID 1 shows a large gap between "container starts" and "PID 1
starts"; here all four independent anchors agree within 0 s and the container's
userspace completed boot 136 ms after PID 1 was exec'd (1053 ms wall including nspawn setup).

### 2.7 Clean root (no honeypot control plane, no fake init, no overlay)

```console
$ nsenter … -- sh -c 'ls -d /var/lib/cortex-pod /run/cortex 2>&1; grep -c overlay /proc/mounts; findmnt -no SOURCE,FSTYPE /'
ls: cannot access '/var/lib/cortex-pod': No such file or directory
ls: cannot access '/run/cortex': No such file or directory
0
/dev/loop4 ext4

os="Ubuntu 22.04 LTS"
absent  /var/lib/cortex-pod
absent  /run/cortex
absent  /usr/local/lib/cortex-agent
absent  /opt/cortex
no pod_pid1/fake-init/cortex-pod files
overlay mounts: 0
root=/dev/loop4 ext4
pkgcount=151
ssh=1:8.9p1-3          # openssh-server installed
```

### 2.8 ps count == /proc count

```console
$ nsenter … -- sh -c 'echo proc=$(ls -d /proc/[0-9]* | wc -l) ps=$(ps -e --no-headers | wc -l)'
proc_dirs=14 ps_lines=14 ps_pids=14
[ OK ] ps count == /proc count (14 == 14)
```

### 2.9 Networking (veth peering)

```console
$ ip -4 -br addr show ve-prod-cortex
ve-prod-cortex@if2 UP             10.66.0.1/24

$ nsenter … -- ip -4 -br addr show; ip route
lo               UNKNOWN        127.0.0.1/8
host0@if10       UP             10.66.0.4/24
10.66.0.0/24 dev host0 proto kernel scope link src 10.66.0.4

$ sudo nsenter … -- ping -c1 -W1 10.66.0.1
1 packets transmitted, 1 received, 0% packet loss, time 0ms
[ OK ] container can reach the VM host over the veth (10.66.0.1)
[ OK ] host ARP resolves the container over the veth   # 10.66.0.4 lladdr e2:c5:…

$ sudo nsenter … -- systemctl is-active ssh
active
```

Host→container **new** connections do not leave the VM host: the VM already
runs an nftables egress filter that drops private ranges
(`ip daddr 10.0.0.0/8 … drop`), and 10.66/24 is inside 10/8. That firewall was
left untouched; sshd is installed and active inside the container, and the task
does not require host→container reachability. See failure notes §4.4.

### 2.10 Resource use (measured)

| metric | value |
|---|---|
| image file | `/var/lib/wetware-hosts/prod-cortex-04.img`, 3.5 GiB apparent, **383 MB allocated** (sparse), `391512` blocks |
| rootfs filesystem | `/dev/loop4`, ext4, 3.4 GiB size, **296 MB used (10 %)**, 2.9 GiB free |
| packages in image | 151 (`dpkg -l`) |
| container boot time | **≈1.1 s wall** (nspawn launch → container systemd `is-system-running`, measured 1053 ms cold); container's own systemd: **136 ms** userspace (`systemd-analyze`) |
| container memory | `memory.current` = **21.4 MB** (20.4 MiB); unit `MemoryCurrent` = 19–21 MB; sum of container process RSS = 71.7 MiB (sum double-counts shared pages) |
| container processes | 13–14 |
| host free memory after boot | 3 911 MB total, 1 931 MB free, 1 723 MB buff/cache, 3 381 MB available |
| host disk | `/dev/sda1` 31 GB, 3.0 GB used, 28 GB free |
| nested KVM | **not available** (`/dev/kvm` absent, `vmx`/`svm` count = 0) — irrelevant for nspawn, noted per task |

---

## 3. Design notes (why it looks like this)

- **ext4 loopback, systemd-managed.** The image is a sparse file; the rootfs
  mount is a real `.mount` unit using `Options=loop`. I first tested that
  systemd 249 mount units support `loop` (probe with a 64 MiB image: mounted
  `/dev/loop5 ext4`), so no manual `losetup`/`mount` survives between runs.
  No overlayfs is used anywhere.
- **Machine name `prod-cortex`, hostname `prod-cortex-04`.** `systemd-nspawn
  --network-veth` names the host-side veth `ve-<machine>`; interface names are
  limited to 15 bytes, so `ve-prod-cortex-04` (17) would be rejected. The full
  hostname still lives in `/etc/hostname` (`prod-cortex-04`) and is what
  `hostnamectl` reports.
- **Explicit `/sbin/init` instead of `--boot`.** With `--boot`, nspawn searches
  for the init binary and executes `/usr/lib/systemd/systemd`, so
  `/proc/1/cmdline` reads `/usr/lib/systemd/systemd`. Passing `/sbin/init` as
  the container command is exactly what the kernel does on a real host, so PID 1
  keeps `comm=systemd`, `cmdline=/sbin/init`; systemd still detects the
  container (`container=systemd-nspawn`, `systemd-detect-virt` works) and boots
  normally. Readiness is polled via the container's `systemctl is-system-running`
  because nspawn without `--boot` signals "started" early.
- **udev runs, sysfs stays read-only.** nspawn masks `/sys` with a small
  read-only tmpfs, so the stock `systemd-udevd.service` skips itself
  (`ConditionPathIsReadWrite=/sys`). A drop-in
  (`/etc/systemd/system/systemd-udevd.service.d/10-wetware-container.conf`)
  clears that condition: udevd then runs as a normal service and is `active`
  (it manages the container's private `/dev`; sysfs remains read-only, which is
  the safe container default — the container cannot poke host sysfs).
- **journald** uses a persistent `/var/log/journal/<machine-id>` inside the
  ext4 image; `--link-journal=try-guest` additionally lets the VM host read the
  container journal with `journalctl -M prod-cortex`.
- **cgroup**: the unit is `Slice=machine.slice` + `--keep-unit`, so the
  container's PID 1 cgroup is
  `/machine.slice/wetware-host-prod-cortex-04.service/payload/init.scope` —
  a child of the container unit's own cgroup (systemd inside the container
  manages its own delegated subtree: `/sys/fs/cgroup/.../memory.current` is
  available for the unit).
- **Network** is configured with systemd-networkd on both ends. The host file
  must sort **before** the vendor `80-container-ve.network` (networkd applies
  the first matching `.network` in lexical order), hence the `70-wetware-…`
  prefix; the container file `20-wetware-host0.network` sorts before the vendor
  `80-container-host0.network`.

---

## 4. Failure notes / gotchas (all encountered and solved unless stated)

### 4.1 Vendor networkd config silently won over ours (fixed)
First iteration named the host file `80-wetware-prod-cortex.network`. The vendor
`/usr/lib/systemd/network/80-container-ve.network` also matches `ve-*` and,
being lexically first, won: the host veth came up with only
`169.254.226.221/16` (IPv4LL) plus odd `192.168.244.241/28`,
`192.168.156.65/28` addresses from that vendor DHCP-server/masquerade config,
i.e. **no 10.66.0.1**. Fix: name it `70-wetware-prod-cortex.network`; verify with
`networkctl status ve-prod-cortex | grep 'Network File'` and
`ip -4 -br addr show ve-prod-cortex`.

### 4.2 `--boot` puts `/usr/lib/systemd/systemd` in `/proc/1/cmdline` (worked around)
See design notes; acceptance check wants `cmdline=/sbin/init`, achieved by
passing `/sbin/init` explicitly.

### 4.3 `machinectl shell` fails inside this container (known limitation, not fixed)
`machinectl shell prod-cortex /bin/sh -c …` connects, but the container-side
session dies:

```
container-shell@1.service: Failed to change ownership of terminal: Input/output error
container-shell@1.service: Failed at step STDIN spawning /bin/sh: Input/output error
```

Reason: machined allocates the pty in the host's devpts instance, while nspawn
gives the container a **private devpts** mount, so the container's systemd
cannot attach the tty. `nsenter -t <pid> -m -u -i -p -n` (the task's listed
alternative) works perfectly and is what the verifier uses; `machinectl
list/status/show` (also listed in the task) all work.

### 4.4 Host→container connections are filtered by the VM's pre-existing firewall
The VM has an nftables egress filter that drops host-originated packets to
`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16` and `169.254.0.0/16`. The veth
addresses are in `10.66.0.0/24`, so `ping 10.66.0.4` / `ssh 10.66.0.4` from the
VM host are dropped **by host policy**, while container→host traffic works
(replies are covered by `ct state established,related accept`). The firewall was
deliberately not modified; veth peering is still proven by both interfaces
carrying their addresses, successful container→host ping, and a resolved ARP
entry. sshd is installed and active inside the container; host reachability was
explicitly not required by the task.

### 4.5 Pre-existing failures on the VM (not caused by this work)
`apparmor.service` is `failed` since VM boot (17:30:07, "At least one profile
failed to load"). It is the only failed unit; all honeypot services stayed
`active` throughout.

### 4.6 No reboot performed
Per task, the VM was not rebooted. The mount unit and the container unit are
`enable`d (`WantedBy=multi-user.target`), so they would come up on a future
boot, but that path was **not** exercised. `SystemMaxUse`/journal rotation and
image fsck on boot are likewise untested.

### 4.7 debootstrap cost
≈4–5 minutes on this VM (public egress, `finished 17:43:38`, 676 log lines).
It is the only slow step; everything after it is sub-second to a few seconds.
The script prints a compact progress line per package phase and skips
debootstrap entirely on later runs.

---

## 5. Files and cleanup

- `ops/nspawn/build_base.sh` — the only file added to the repo by this
  prototype (plus this README).
- On the VM the script creates/owns:
  `/var/lib/wetware-hosts/prod-cortex-04.img`,
  `/var/lib/wetware-hosts/prod-cortex-04/`,
  `/var/lib/wetware-hosts/reports/{debootstrap,verify}.log`,
  `/etc/systemd/system/var-lib-wetware\x2dhosts-prod\x2dcortex\x2d04.mount`,
  `/etc/systemd/system/wetware-host-prod-cortex-04.service`,
  `/etc/systemd/network/{70-wetware-prod-cortex,80-wetware-prod-cortex}.network`.
- Stop: `sudo bash build_base.sh stop`.
- Remove everything: `sudo FORCE=1 bash build_base.sh destroy`
  (stops the unit, disables/removes the unit files, unmounts, detaches loop,
  deletes the image). This is the only destructive command; without `FORCE=1`
  it refuses.

## 6. Verification cheat-sheet

```bash
UNIT=wetware-host-prod-cortex-04.service
MACHINE=prod-cortex
PID=$(sudo machinectl show -p Leader --value $MACHINE)

sudo systemctl status $UNIT --no-pager          # unit, cgroup, Main PID
sudo machinectl list; sudo machinectl status $MACHINE
cat /proc/$PID/comm                             # systemd
tr '\0' ' ' < /proc/$PID/cmdline                # /sbin/init
cat /proc/$PID/cgroup                           # /machine.slice/$UNIT/payload/init.scope
sudo findmnt -no SOURCE,FSTYPE /var/lib/wetware-hosts/prod-cortex-04   # /dev/loopN ext4

sudo nsenter -t $PID -m -u -i -p -n -- /bin/sh -c '
  systemctl status --no-pager; hostnamectl; journalctl -b --no-pager | head;
  systemctl list-units --type=service --state=running --no-legend'

sudo journalctl -M $MACHINE -b --no-pager       # host-side container journal
sudo bash build_base.sh verify                  # full 36-check suite, exit code
```
