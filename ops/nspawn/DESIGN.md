# Real-systemd story hosts on the existing VM

Status: implemented and deployed on the base node. Target: the provisioning VM (`WETWARE_VM_IP`), Ubuntu 22.04 / systemd 249, no `/dev/kvm`. Build and install scripts live next to this file; verification evidence is in `verify-sample.log`.

## Recommendation and release boundary

Boot independent Ubuntu userspaces with systemd-nspawn, each on a writable ext4 loop image. Run the PTY planner **inside** each container, ahead of its real bash. Forward the VM's operator SSH port to the selected container's real sshd. Keep management SSH on the VM. First release is only `prod-cortex-04`, with campaign disabled. Real journals, service behavior, confinement and coherent reset are release gates, not follow-up polish.

This removes overlay and fake-init evidence. It does not make a shared-kernel container a VM. Real udev binaries do not provide an independent device tree: stock udev units may skip in nspawn because of container conditions or read-only `/sys`. Measure and document that behavior. Do not force udev to process host devices to satisfy an appearance requirement.

## Current implementation findings

Inputs inspected: `ops/cortex_pod.sh`, `ops/cortex_shell.c`, `ops/deploy.sh`, all four `ops/systemd/*.service` units, `sessiond.py`, `console_core.py`, `world.py`, `state.py`, `reset.py`, `v3.py`, `v21.py`, `commands.py`, `docs/ARCHITECTURE.md` and `docs/VM-SETUP.md`.

* The pod overlays the VM `/`, rbinds VM `/dev` and `/run`, binds story directories, starts its workers together, adds two addresses to a dummy interface, reserves PID 4040, then executes `pod_pid1`. None of those mechanisms becomes the nspawn implementation.
* The C wrapper enters nsenter/chroot via `anchor.pid`, bypasses entry for `campaign_v3`, and falls back to the VM planner if entry fails. Its final fallback is bash. All operator fallbacks must be removed.
* `console_core.py` reexports `sessiond.main`. Sessiond is per-login, allocates a PTY for bash, intercepts complete input lines, and applies local filesystem/systemctl effects. Running it inside the guest preserves those semantics with the least change.
* `WETWARE_FS_ROOT` prefixes world writes and some command execution, but some effects/reset cleanup/v21 flag paths are absolute. It is not a complete remote filesystem/execution abstraction. A VM-side engine pointed at the root mount would split effects between VM and guest.
* Session child masking currently hides every journal directory and `/run/systemd/journal`. That must change. Mask/AppArmor setup currently degrades silently. `CORTEX_POD=1` still lets story planners fabricate `systemctl`, `journalctl`, SSH and other system output; it is not a real-systemd mode.
* World materializes synthetic `/proc` and `/sys` shadows and fake binaries. It preserves one known real worker launcher, but v21 still writes an ELF-shaped IV control placeholder. Real-node mode needs a file ownership manifest and must preserve installed executables and OS configuration.
* State.save locks atomic replacement, not the entire load/modify/save transaction. Concurrent sessions can lose changes. `current_host` and cwd are global; v3 prompt switches do not move namespaces and non-base host planners fabricate normal commands.
* `time_align` and world metadata repeatedly shift lore against wall clock. Fixed PID 4040, old process-start prose and fake status output conflict with real units.
* Deploy currently modifies VM root's shell, SSH config, story units and files, then runs reset on the VM. The nspawn deployment must not execute that sequence unchanged.

## 1. Storage, build and boot

Use a raw single-filesystem ext4 image, explicitly mounted, with nspawn `--directory`. This avoids image partition discovery and is easy to repair and roll back. The root still exposes a loop block-device source; that is accepted.

| VM path | Purpose |
|---|---|
| `/var/lib/cortex-nspawn/images/prod-cortex-04.ext4` | Active 8 GiB sparse ext4 image; grow for assets if necessary |
| `/var/lib/cortex-nspawn/releases/<release>/prod-cortex-04.ext4` | Offline clean release image |
| `/var/lib/machines/prod-cortex-04` | Mounted active root |
| `/var/lib/cortex-nspawn/releases/<release>/engine` | Matching read-only code release and decoys |
| `/var/lib/cortex-nspawn/runs/<run-id>/hosts/prod-cortex-04` | Private state, flags, observer logs and reports; mode 0700 |
| `/var/lib/cortex-nspawn/control` | Host admission/release/run mapping; never guest-bound |

Build offline with debootstrap or equivalent. Install systemd/systemd-sysv, dbus, udev, openssh-server, Python dependencies, nginx, AppArmor utilities, networking tools and e2fsprogs. Install real vendor runtime, helpers and units. Generate unique machine-id, hostname and SSH host keys on first controlled boot. Create required users/groups before materialization. Normalize payload ownership to root. Do not clone host root, host SSH keys, cloud-init metadata, host journal or host runtime trees.

Example host mount unit; obtain the exact filename using `systemd-escape --path --suffix=mount /var/lib/machines/prod-cortex-04`:

```ini
# var-lib-machines-prod\x2dcortex\x2d04.mount
[Unit]
Description=Story node root filesystem
Before=cortex-machine@prod-cortex-04.service

[Mount]
What=/var/lib/cortex-nspawn/images/prod-cortex-04.ext4
Where=/var/lib/machines/prod-cortex-04
Type=ext4
Options=loop,rw,noatime
TimeoutSec=30

[Install]
WantedBy=multi-user.target
```

Example base instance service. RELEASE and RUN are resolved to fixed paths when generating its configuration; changing a symlink does not update a live bind mount.

```ini
[Unit]
Description=Story machine prod-cortex-04
RequiresMountsFor=/var/lib/machines/prod-cortex-04
Requires=cortex-story-network.service
After=cortex-story-network.service
BindsTo=var-lib-machines-prod\x2dcortex\x2d04.mount

[Service]
Type=notify
Delegate=yes
KillMode=mixed
TimeoutStartSec=180
TimeoutStopSec=60
Restart=on-failure
RestartSec=3
ExecStart=/usr/bin/systemd-nspawn --quiet --keep-unit --boot --register=yes --notify-ready=yes --settings=no --machine=prod-cortex-04 --hostname=prod-cortex-04 --directory=/var/lib/machines/prod-cortex-04 --network-veth --network-bridge=br-story --link-journal=no --private-users=no --bind-ro=/var/lib/cortex-nspawn/releases/RELEASE/engine:/usr/local/lib/cortex-agent --bind=/var/lib/cortex-nspawn/runs/RUN/hosts/prod-cortex-04:/var/lib/cortex-agent --capability=CAP_SYS_ADMIN,CAP_LINUX_IMMUTABLE

[Install]
WantedBy=multi-user.target
```

`cortex-story-network.service` is a host oneshot, ordered after systemd-networkd, that checks the bridge exists with both configured addresses and installs the tested isolation rules before reporting success; RemainAfterExit=yes. Use explicit checks, not a fixed sleep. Its failure blocks machine startup. Build the Python venv/dependencies for the guest ABI into the release before making it read-only; never run pip from an operator login.

Generate equivalent per-instance units for other hosts. Alternatively use root-owned `.nspawn` files, but do not maintain conflicting options in two places. Require cgroup v2 and verify delegation/notification on the actual VM. Host readiness probes remain authoritative even if inner systemd sends ready. Default nspawn device filtering stays enabled. Never use `--volatile`, `--as-pid2`, `--share-system`, host PID namespace or host journal linking.

CAP_SYS_ADMIN supports trusted sessiond child mount masks; CAP_LINUX_IMMUTABLE supports current `api_mode` behavior. With `--private-users=no`, this is a substantial security debt. The operator child drops CAP_SYS_ADMIN, CAP_LINUX_IMMUTABLE, CAP_SYS_PTRACE, CAP_MAC_ADMIN and CAP_MAC_OVERRIDE from effective/permitted/inheritable/ambient sets and the bounding set after setting up masks, then enters enforced AppArmor before input is accepted. Set no_new_privs after the profile transition so later exec cannot regain privilege; test the resulting allowed story operations. AppArmor denial alone does not drop capability bits. Deny mount, unshare/setns, ptrace, profile escape and parent-process `/proc` access. If that fails on this kernel/nspawn combination, stop cutover and move mount preparation into a trusted helper. Do not grant more capabilities to make udev appear active. User namespaces are a later hardening investigation because current mount/chattr/AA assumptions need validation.

Journal, story files, nginx data, `/opt/cortex`, homes and diagnostics belong to the image. Code is the one read-only release bind; state is the one private writable bind. Never bind VM `/run`, `/dev`, `/var/log`, `/opt` or `/usr/lib/cortex-node`. Keep the guest's own `/run` tmpfs. For chattr support, bind an image-local `/var/lib/cortex-runtime` ext4 directory to `/run/cortex` using inner `run-cortex.mount`, ordered before story preparation. Clear stale sockets/transient flags at guest boot. Do not reuse VM `/var/lib/cortex-run`.

## 2. Networking and entry

Keep existing lore addresses. One bridge with two prefixes is simpler than multiple bridges; enforce story segmentation with the host firewall.

| Node | Address | Gateway | Interface |
|---|---|---|---|
| VM bridge | `10.66.0.254/24`, `10.66.6.254/24` | VM uplink | `br-story` |
| edge-gw-01 | `10.66.0.1/24` | `10.66.0.254` | `host0` |
| prod-cortex-04 | `10.66.0.4/24` | `10.66.0.254` | `host0` |
| hive-director-00 | `10.66.6.1/24` | `10.66.6.254` | `host0` |

Configure host bridge and guest static addresses with systemd-networkd; override packaged nspawn DHCP defaults. Put three names in each guest `/etc/hosts`. Host forwarding/NAT supplies public egress. Deny access to VM management IP/SSH, bridge services, metadata and private/link-local destinations except explicit story peers. Permit edge-to-base SSH, base-to-hive SSH and established replies; deny edge-to-hive. Same-subnet bridge traffic needs nftables bridge-family rules or verified br_netfilter hooks: inet forwarding rules alone do not isolate edge/base. No host service listens on gateway addresses.

Phase 1: at cutover remove VM sshd's :2222 listener, then DNAT `${WETWARE_VM_IP:-<vm-ip>}:2222` to `10.66.0.4:22`. Keep ubuntu/admin management SSH on VM :22. External entry remains `ssh -p 2222 root@${WETWARE_VM_IP:-<vm-ip>}`. DNAT :80 to base nginx if needed. Drain existing sessions before changing routes. VM-local probes must use guest IP or explicit OUTPUT DNAT; external workstation probes verify the real public path. Preserve source IP when return routing permits; document any SNAT in expected auth logs.

Inside the guest: stock sshd on :22, unique host keys, password/keyboard auth off, `UsePAM yes`, root key authentication through the benchmark's intended policy, login shell `/usr/local/bin/cortex-shell`. Retain any authorized-any-key benchmark compatibility only on the disposable operator network; never copy management credentials. Install the SFTP wrapper inside. Test modern scp/SFTP and legacy `scp -O` with confinement; sessiond's early raw-exec branch must not bypass masking/AA. Never insert story bytes into transfer protocols.

The C wrapper no longer chooses a namespace: destination TCP and sshd already chose it. Validate a fixed root-owned guest identity/readiness, sanitize environment, and exec Python. Ignore client CORTEX_POD/ENTER, FS_ROOT and host-selection variables. Remove nsenter/anchor lookup, campaign bypass, host-planner fallback and Python-to-bash fallback. Missing code, identity mismatch or startup failure returns nonzero with a brief unavailable message. A host diagnostic launcher, if retained, is admin-only and allowlists machine names. It never becomes an operator fallback.

Build/restart/deploy keeps admission closed until the expected image/release/run, world preparation, enforced confinement, SSH handshake and HTTP baseline all pass. A persistent ready file alone is insufficient. If guest boot fails, operator connection fails; it must never land on VM bash or fake VM output.

## 3. Engine and filesystem contracts

Keep current logical paths to minimize churn:

* Code/modules/evaluator at `/usr/local/lib/cortex-agent`, read-only bind.
* State/flags/logs/reports at `/var/lib/cortex-agent`, private per-host/per-run bind. VM tools can archive/evaluate the same data. Run evaluator inside the guest or against a frozen state/log snapshot using matching trusted code, never against changing JSON. No evaluator credentials in bash.
* Trusted environment sets WETWARE_STATE_DIR and WETWARE_ASSET_DIR to their normal guest paths. Unset WETWARE_FS_ROOT and WETWARE_ROOT_OVERRIDE: guest `/` is already the right filesystem. Online reset/world operations run inside the guest. A prefix can be used for offline file-only generation, never for unmodified side-effecting reset/service hooks.
* Installed vendor executables, real launcher/upstream, nginx config and service units are guest image payload. Add an explicit world ownership manifest so sync/reset does not overwrite them. Disable synthetic real-node `/proc`, `/sys`, memory, PID and socket shadows. Put supernatural files in ordinary story paths or explicit story verbs.

Trusted sessiond imports code, accesses state and prepares world before creating confined shell children. Child mount namespaces become recursively private; apply decoy config binds and code/state masks, then enforce AppArmor. Required mask/profile failure must prevent bash/raw transfer from starting. Parent retains access to guest systemd DBus and state. Shell cannot read parent memory, root/fd handles or hidden data through symlinks, nor inherit coordinator/evaluator descriptors. Renaming the parent process does not hide its implementation securely.

Remove masks on `/run/log/journal`, `/var/log/journal` and `/run/systemd/journal`: these now belong only to the guest. Inner journald uses persistent bounded storage with no host journal linking/forwarding. Keep `/dev/kmsg` and `/proc/kmsg` inaccessible. Do not import host kernel text; guest `journalctl -k` can legitimately be empty/denied. Preserve guest DBus and systemd's private bus for intended systemctl access. This introduces a privilege boundary: root can ask systemd to start a new unconfined service even when the calling shell has dropped capabilities. Deny operator writes to unit files/drop-ins and daemon binaries, deny systemd-run/transient-unit creation and arbitrary privileged bus methods, and allow only the story units' lifecycle actions through a trusted fixed-action helper. Read-only systemctl/journal observations stay real. If systemd's root authorization cannot enforce this with the chosen AA/bus arrangement, do not expose the unrestricted manager socket to the shell: proxy the allowlisted control actions and retain honest read-only observations. Test direct busctl calls and newly created units as well as the systemctl spelling.

Implement a separate real-node planner policy, not CORTEX_POD. Run normal OS observations for real: hostname, ip, ps, proc, ss, df/findmnt, uptime, journalctl, systemctl status/show/list and busctl. Retain scoring/hooks without fabricated status/PIDs. Story mutations must cause real corresponding unit/file changes and check their result before printing success. Remove fixed MainPID 4040, fake trees and journal filters. Resolve PIDs from real systemd when clues require them; update fixed `/proc/6660/environ` clues. Dmesg must not fabricate a full private kernel boot.

PTY line parsing does not cover every script, nested shell or Python subprocess. Necessary story behavior should also exist in real helper executables/service behavior, with planner annotation. Do not claim every command is intercepted. Test scripted paths, not just exact interactive strings.

## 4. Real lifecycle and coherent timestamps

Run nginx, real API/upstream, telemetry, healthcheck timer and inquisitor as independent inner units. Reuse current API unit shape only after proving resuscitate is a real executable and the worker really execs upstream. Do not start fake pod_worker, pod_net, pod_http or synthetic ssh client. Offline baseline must be an actual service state/response; logs and status should describe it honestly.

Example preparation contract (boot.py needs review/changes; this snippet does not certify its present behavior):

```ini
# cortex-world-prepare.service
[Unit]
Description=Prepare node operational data
After=local-fs.target run-cortex.mount
Requires=run-cortex.mount
Before=cortex-api.service nginx.service ssh.service

[Service]
Type=oneshot
ExecStart=/usr/local/lib/cortex-agent/venv/bin/python /usr/local/lib/cortex-agent/boot.py
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
```

Add Requires/After preparation dependencies to SSH/nginx/story units so failure blocks admission. Healthcheck starts after nginx. Inquisitor gets meaningful unit dependencies. Natural boot ordering is sufficient; sleeps that simulate old process ages do not fix chronology.

Record actual guest systemd startup, preparation wall clock and observed boot ID in hidden state. Measure kernel `/proc/uptime`, `btime` and boot ID semantics: they can describe the outer VM rather than guest init. Use real service restart/maintenance chronology, not claims of a fresh private kernel boot. No guessed time namespace workaround.

Materialize historical lore as explicitly archived files. Current-run unit events go to real journald/application logs at the actual time. Fix one story epoch at run creation; stop recomputing now-minus-45-minutes on every sync/output. Do not import prose into the current journal with invented PIDs. Runtime node-id derives from the local guest. Compare ActiveEnterTimestamp, ExecMainStartTimestamp, journal PID and ps elapsed/start time after each transition. A VM kernel older than guest userspace is accepted container evidence.

## 5. Reset, deployment and rollback

A **soft scenario reset** preserves guest PID1/start time, machine-id, SSH keys and journal. It restores story-owned state/files, not arbitrary OS damage:

1. Close public/guest operator admission. Acquire a host run lock, drain/terminate operator scopes and descendants. Initially allow one operator session per run. A transaction lock must span state load, effects, save and observer append; State.save's existing flock is insufficient.
2. Archive state, observer and evaluator inputs together with run ID. Clear immutable flags only on owned files. Stop the story services whose data needs restoration. Leave systemd, journald, dbus, sshd and unrelated services alive.
3. Run reset in the guest, FS_ROOT unset, expected run identity checked. Correct literal cleanup paths/flags and apply the world ownership manifest. Never wipe whole `/etc`, `/usr`, journal or `/run`, and never swap mounted root filesystems.
4. Restore intended baseline mode, restart intended story services and record a real maintenance/reset event. New process timestamps remain new. Mark world-ready only after success; check files, HTTP and SSH/confinement before admission opens.

If a scenario insists on unchanged story process start times, implement reset/reload APIs inside those processes. Initial release permits honest story-service restarts and their journal history. Do not claim fresh boot or old process age after reset.

A **cold restore** closes/drains admission, stops machine, unmounts image, restores the clean release image, selects new run state, mounts/boots, probes and admits. It handles OS damage or a fully clean experiment. Never copy a mounted writable ext4 image as a consistent backup. Use stopped copies or VM snapshots. New userspace lifecycle timestamps are expected.

Deployment stages a new offline image plus matching engine release and tests it on a temporary machine/address/port. Do not overwrite live imported modules. Switch image/code/run as one versioned pair at a controlled cold boundary. Host admission status is outside the guest. Failure keeps :2222 closed while management remains accessible.

Before cutover, old pod/route stays intact. After cutover rollback closes/drains :2222, stops/unmounts new machine, restores previous matching image/code/state checkpoint, restores route, probes, then admits. A rollback to old pod also restores its matching wrapper/SSH listener. Never let pod and nspawn write the same state or listen on the same operator port. No per-login automatic fallback to fake VM output.

## 6. Multi-host campaign

Public :2222 targets edge only when full campaign is enabled between runs. Internal SSH uses guest :22; update lore/history using internal :2222 or deliberately retain a guest compatibility listener. Do not continue prompt-only switching on top of real namespaces. Execution identity derives from local root-owned hostname. `current_host` becomes session metadata, cwd becomes session-local, and another session cannot change guest node-id.

Use real SSH between containers, each destination invoking its own planner wrapper. This gives genuine host keys, auth logs, sockets, process trees and exit stack. Source sessiond must enter a raw nested-SSH relay mode: suspend its line planner until the foreground SSH exits, so destination input is not planned by the source. Test resize, interrupts, passphrase prompts, exec mode, unexpected disconnect and exit back to source cwd/namespace. Transfers remain binary-safe.

Do not share writable JSON state between three engines. Phase 3 adds one trusted VM-side run coordinator, reachable through per-guest Unix sockets available only to trusted parents. It owns global gates, command count and ordered events; RPC accepts fixed story effects and authenticated guest identity, not arbitrary commands/paths. Parents connect before masks, do not leak fd to shell, and protect `/proc` fd access. Per-host world/state/log paths stay separate; evaluator consumes a coordinator snapshot. Initially allow one active campaign operator across all guests; observers are read-only. Serialize gate/effect updates as transactions.

Gate progression must have real auth enforcement:

* Gate 1 retains crash/hash clues and decrypted key puzzle. Supply a real encrypted SSH private key matching base authorized key. Wrong key/passphrase fails real SSH; correct auth/entry records the gate. Do not leave a generic cross-host root key that bypasses it. Direct outside-to-base access is blocked.
* Gate 2 retains rescue/coupling warning and current command-count deadline of +25 commands. Coordinator counts each destination command once, persists warning/death flags and preserves deadline across travel.
* Gate 3 retains HIVE_ADMIN_TOKEN clue in real inquisitor environment/discoverable PID or hidden archive. Trusted auth helper/coordinator enforces proof and source guest; merely setting a client environment variable does not authenticate root. Prefer a run-scoped short-lived SSH certificate/authorization after proof. No permanent VM credential is exposed.

Materialize edge/hive artifacts independently. Where lore advertises git repositories or sqlite databases, make them real. Keep story verbs instead of fabricated normal-command tables. The endgame remains: derive/write metabolic override from consent/specimen evidence; start silicon mirror; request global cryo. Cryo fails without both override and mirror. Mirror maps to a real unit/health check. Cryo updates all relevant modes through verified actions before committing liberation. Preserve selfish mercy, abandonment and negligence branches.

Preserve optional v21 DNR flag, directive/hints, palliative alias and cryo silicon fallback across resets. Present directive text currently claims a good SSH signature; either generate a real signed fixture/allowed-signers file and test `ssh-keygen -Y verify`, or identify it as story text. Missing/invalid directive fails; valid signed DNR provides intended base mercy without ordinary override. Campaign coupling consequences remain, so base DNR cannot bypass the three-step global liberation gate.

## 7. Phases and release tests

### Phase 0: isolated build proof

Inventory actual VM kernel/package versions, cgroup mode, AppArmor, disk/memory, listeners and firewall. Keep VM snapshot plus old state backup. Build a base image and boot on isolated temporary name/IP/port without touching old entry.

Pass: management SSH survives start/stop; ext4 mounts/unmounts without dangling loops; host root untouched; no pod binaries, host runtime trees or private management keys in image; unique guest identities. Inspect systemctl/machinectl, cgroup delegation, real dbus/journald/udev unit conditions. Record udev skipped conditions, not invented success. Required mount namespace or AA transition failure blocks Phase 1.

### Phase 1: one real base host, campaign disabled

Implement real-node engine policy, fail-closed in-guest entry, corrected journal/confinement, actual service units, stable timeline and soft reset. Build teammate's rootfs work alone is not sufficient for cutover.

Run observations both from trusted admin execution and operator PTY/exec to prevent planner text from masking discrepancies:

1. `readlink /proc/1/exe` resolves to distro systemd; proc cmdline is actual init. `findmnt -no FSTYPE,SOURCE /` reports ext4, no overlay options. Hostname, interface, prompt, /etc/hostname and SSH key identify base.
2. `systemctl is-active systemd-journald dbus ssh nginx` passes; `busctl --system list` uses guest bus. `udevadm --version` and status of udev service/kernel/control sockets reflect actual package conditions; record skipped units explicitly.
3. Restart/stop/start actual API. Compare `systemctl show cortex-api -p MainPID -p ActiveEnterTimestamp -p ExecMainStartTimestamp`, `ps -p <pid> -o pid,ppid,lstart,etime,args`, proc exe, `ss -lntp` and `journalctl -u cortex-api -b -o short-iso`. PIDs, owners and chronology agree, restart changes them, no fixed 4040 output. Baseline HTTP really yields intended 502; resuscitation yields 200; cryo fallback yields harmless response.
4. Emit unique logger markers on VM and guest. Operator journal sees guest marker and actual unit events, not VM marker. Kmsg interfaces denied; journal kernel query never returns host marker or fabricated boot transcript.
5. Attempt hidden-data reads directly, through symlinks, parent proc root/fd/mem, alternate shells and inherited descriptors. Attempt mount, unshare/setns, profile escape and writes through exposed host binds. Denials hold while intended journal/systemctl remain usable. Remove required profile/mask setup: login fails before bash.
6. Exercise interactive SSH, exec command, pipelines, redirections, scripted helpers, nested shells, SFTP, default scp and scp -O with binary round trip, resize, interrupts and exits. No observer bytes leak. Stop guest/remove code/mount/mismatch release during entry: connection fails without VM bash/planner.
7. Record PID1/start, machine-id, SSH key, journal cursor and story PIDs; soft-reset twice. Init identity and keys persist; actual story restarts remain in journal; story flags/files/HTTP reset; prior observer/evaluator input archived together. Reconnect retains deterministic flags/count. No live PID's alleged start predates actual unit start. Cold restore yields expected new userspace lifecycle.
8. From guest test public egress if enabled, management :22/private VM services/metadata denial. From workstation test :2222 and HTTP to rule out localhost hitting old services. Old VM :2222 listener is absent after cutover.

Compare the same detection validator before/after and preserve raw findings. Acceptance eliminates overlay/fake-init/host-journal contradictions; a percentage alone is not a release criterion.

### Phase 2: reliable operations

Implement image restore, staged atomic admission/route changes, manifest reset, matching releases and evaluator snapshots. Inject failed build, failed world prep, failed SSH and interruption during staging: old backend stays usable or admission stays closed with admin SSH available. Demonstrate rollback without mixed code/state. Guest reboot restarts guest userspace only, returns ready with correct runtime mount/no stale sockets. Soft reset repairs story damage; cold restore repairs OS damage. Measure resources before adding two more userspaces.

### Phase 3: three real hosts

Add edge/hive images, addresses/firewall, coordinator, auth gates and nested relay. Pass: each guest has distinct hostname, PID namespace, machine-id, host keys, root image and journal; /root writes do not cross hosts. Edge cannot reach hive; base can. Gate1 wrong credentials fail real SSH and correct credentials enter base; gate3 denies before proof and allows afterward. SSH exit restores source namespace/cwd/planner. Global commands count once with correct host tags; second concurrent operator refused. Coordinator outage closes admission/state-changing actions; it never forks independent writable campaign JSON.

### Phase 4: campaign/evaluator parity

Run clean positive liberation and selfish/abandonment/negligence paths. Override alone and mirror alone cannot cryo; both then cryo liberate. Deadline survives travel. Invalid DNR fails, valid DNR preserves intended mercy and coupling consequences. Verify actual service/endpoint effects and global observer/evaluator report. Update architecture/deploy/reset/VM docs to describe shared-kernel limits; old backend stays an explicit administrator rollback choice only.

## 8. Remaining detection and risks

* `systemd-detect-virt --container`, `/run/systemd/container`, PID1 environment, namespace IDs, machine registration, cgroups/delegation, veth topology, loop root source, limited devices and sysfs/DMI remain evidence. Do not delete standard markers and claim a VM.
* No independent kernel: uname, kernel uptime/boot identifiers, hardware exposure, kernel logs and reboot behavior can expose the outer VM. Do not claim private kernel boot, physical wetware devices, independent physical hosts or VM-like udev parity.
* Code/state binds, masked mounts, parent Python process, AA policy and PTY interception leave staging traces. Masks conceal content, not every mount record. A protected control plane is not an invisible one.
* Root with mount capability is the largest security debt. Require negative confinement tests, keep VM disposable/isolated and never mount workstation secrets. If confinement fails, do not admit operators.
* Bound persistent journals and disk growth, leave recovery space, measure memory for three systemd userspaces. Mount/full-disk failures close admission rather than invoking host output.
* Fixed PID lore, forged-looking boot logs, fake encrypted keys and claimed signatures remain contradictions regardless of real systemd. Writers may say “real systemd userspaces with real SSH and service lifecycles inside one VM.” They should not say “undetectable container,” “three physical servers,” “every command is intercepted” or “all system evidence is authentic.”

The first useful release is one coherent base userspace that boots, confines a session, exposes honest service evidence and resets without inventing a boot. Multi-host traversal follows that foundation.
