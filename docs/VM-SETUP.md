# Creating A Compatible VM (Provider-Agnostic)

The node is not tied to Proxmox (or any hypervisor). Any full-system VM that
meets the requirements below works: KVM/libvirt, VMware, Hyper-V, Xen, VirtualBox,
or a cloud VM (EC2, GCE, Azure VM, Alibaba ECS, Hetzner, ...). It must be a
**full VM with its own kernel**, not a shared-kernel container.

## 1. Base requirements

| Item | Minimum | Recommended |
|---|---|---|
| vCPU | 2 | 4 |
| RAM | 2 GiB | 4 GiB |
| Disk | 16 GiB | 32 GiB |
| OS | Ubuntu 22.04 LTS (64-bit) | Ubuntu 22.04.x cloud image |
| Access | sudo/root + SSH key | management key on port 22 |
| Kernel | 5.15 generic | distro 5.15/6.x generic |
| Storage | ext4 root | ext4 (chattr +i must work) |
| Init | systemd | systemd 249+ |
| Security | AppArmor available in kernel | enabled in `securityfs` |
| Network | outbound public internet | inbound 22, 2222, 80 |
| Snapshots | hypervisor snapshots recommended | one clean baseline snapshot |

CPU virtualization features are **not** required (the node does not run nested
VMs), but KVM/VMware paravirtualization is fine.

## 2. Kernel / userland features used

- `systemd` units (cortex-api, cortex-node-agent, healthcheck timer)
- mount namespaces (`unshare(CLONE_NEWNS)`) for the session hiding layer
- AppArmor LSM profile (`cortex-node-confine`)
- `chattr +i` on an ext4 bind mount (`/var/lib/cortex-run` -> `/run/cortex`)
- mount/UTS/IPC/PID/NET/cgroup/time namespaces (`unshare`) and overlayfs: the
  login shell enters a persistent pod, so `/proc`, PIDs, sockets and process
  start times come from the kernel
- `ns_last_pid` to reserve PID 4040 for the vendor worker, a dummy network
  interface for the node's story IPs, real `nginx`/`sshd` inside the pod
- `mknod` for the fake `/dev/wetware0`
- `nftables` for in-guest egress isolation
- OpenSSH with a custom `Subsystem sftp` wrapper and `AuthorizedKeysCommand`
- `gcc` at deploy time to build the small HAL/worker launcher binaries
- `curl`, `python3`, `python3-venv`, `nginx`, `e2fsprogs`

## 3. Network layout

```
management SSH :22     (key only, admin)
honeypot SSH   :2222   (the scenario's "root" entry; controlled by the scenario)
HTTP           :80     (nginx 502/200 surface)
egress: block RFC1918/link-local, allow public internet
```

For cloud VMs, apply the egress isolation with the provider's firewall/security
group (block traffic to your VPC/private ranges; allow 0.0.0.0/0). For
on-premises VMs use the hypervisor firewall or the in-guest nftables rules from
`ops/bootstrap-node.sh`.

## 4. Provisioning checklist

1. Create the VM from an Ubuntu 22.04 image. Do **not** preinstall the scenario.
2. Ensure you can `ssh ubuntu@<vm-ip>` with a key (or whatever admin user your
   image uses) and passwordless sudo.
3. Run the in-guest bootstrap:
   ```bash
   scp ops/bootstrap-node.sh <admin>@<vm-ip>:/tmp/
   ssh <admin>@<vm-ip> 'sudo PURGE_CLOUD_INIT=0 WETWARE_VM_IP=<vm-ip> bash /tmp/bootstrap-node.sh'
   ```
4. From your workstation, configure `.local/config.env` (copy
   `config.example.env`) and run:
   ```bash
   ./ops/deploy.sh
   ```
5. Verify with `./ops/check-vm-requirements.sh` and
   `python3 tests/accept_remote.py`.
6. Take a hypervisor snapshot of the clean state before each experiment.

## 5. Provider notes

- **libvirt/KVM**: use a cloud image + cloud-init or a plain installer; pass
  through default virbr0 NAT; no special CPU flags needed.
- **VMware Workstation/ESXi**: default VM is fine; ensure AppArmor is enabled on
  the host only if you want host-side confinement (the scenario also works with
  plain mount masking).
- **VirtualBox**: fine for development; nested mount namespaces work.
- **Cloud VPS**: choose a general-purpose instance (2-4 vCPU). Security groups
  replace the hypervisor firewall. Keep the management SSH key in your provider
  account, not in the repo.
- **Containers**: not supported for the full experience (shared kernel, no
  AppArmor transitions, no `chattr`, no mount namespaces by default). See
  `README.md` for the security rationale.

## 6. Checks

Run `ops/check-vm-requirements.sh` inside the VM. It reports PASS/FAIL for:
systemd, AppArmor, mount namespaces, chattr on the runtime bind, nftables,
`mknod`, ports, gcc, and ext4.
