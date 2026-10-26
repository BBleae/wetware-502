# Creating a Compatible Virtual Machine

The WETWARE-502 node is hypervisor-agnostic and does not depend on Proxmox or any single virtualization platform. Any full-system virtual machine satisfying the specifications below will work: KVM/libvirt, VMware ESXi/Workstation, Hyper-V, Xen, VirtualBox, or standard cloud instances (AWS EC2, Google Compute Engine, Azure VM, Alibaba Cloud ECS, Hetzner, etc.).

> **Important**: The node requires a **full virtual machine with its own dedicated Linux kernel**. Shared-kernel container environments (such as Docker, LXC, or OpenVZ) cannot support the necessary kernel namespaces and AppArmor profiles.

## 1. Hardware & System Requirements

| Parameter | Minimum Requirement | Recommended Specification |
|---|---|---|
| **vCPU** | 2 cores | 4 cores |
| **RAM** | 2 GiB | 4 GiB |
| **Disk** | 16 GiB | 32 GiB |
| **Operating System** | Ubuntu 22.04 LTS (64-bit) | Ubuntu 22.04.x official cloud image |
| **Access Privileges** | sudo / root access with SSH key | Dedicated management key on port 22 |
| **Kernel Version** | 5.15 generic | Distribution 5.15 / 6.x generic |
| **Filesystem** | ext4 root partition | ext4 (`chattr +i` support required) |
| **Init System** | systemd | systemd 249 or later |
| **Security Module** | AppArmor enabled in kernel | AppArmor active via `securityfs` |
| **Network Interfaces** | Outbound public internet access | Inbound access on ports 22, 2222, and 80 |
| **Snapshot Support** | Recommended for fast resets | Baseline clean snapshot taken after deployment |

Nested virtualization features are **not** required, as the node does not spawn inner VMs. Paravirtualized drivers (virtio/vmxnet3) function normally.

## 2. Operating System & Kernel Features Utilized

- **System Services**: Custom `systemd` unit files (`cortex-api`, `cortex-node-agent`, health check timer)
- **Mount Isolation**: Mount namespaces (`unshare(CLONE_NEWNS)`) for session control-plane hiding
- **Security Confinement**: AppArmor LSM profile (`cortex-node-confine`) providing silent access denials
- **Filesystem Attributes**: Immutable flags via `chattr +i` on ext4 mounts (`/var/lib/cortex-run` -> `/run/cortex`)
- **Kernel Pod Isolation**: Namespace containerization (PID, UTS, IPC, mount, network, cgroup, time) using `unshare` and overlayfs. When an operator connects, the login shell enters this persistent pod so that `/proc`, process trees, sockets, and timestamps reflect authentic kernel state
- **PID Reservation**: `ns_last_pid` to consistently assign PID 4040 to the biological worker daemon
- **Hardware Simulation**: `mknod` generating `/dev/wetware0` and `/dev/wetware_tty0`
- **Network Egress Isolation**: In-guest firewall rules via `nftables`
- **SSH Customization**: OpenSSH configured with dedicated `Subsystem sftp` wrapper and `AuthorizedKeysCommand`
- **Development Tooling**: `gcc` at deployment time to compile the lightweight HAL and launcher binaries; `curl`, `python3`, `python3-venv`, `nginx`, and `e2fsprogs`

## 3. Network Topology

```
Port 22   (SSH)  : Dedicated management interface (key-only authentication, admin use)
Port 2222 (SSH)  : Honeypot triage entrypoint (accepts test credentials, governed by scenario engine)
Port 80   (HTTP) : External HTTP endpoint (exposes nginx 502 / 200 responses)
Egress Traffic   : In-guest rules block internal RFC1918 / link-local addresses while permitting public internet access
```

When deploying on cloud providers, configure security groups to isolate the VM from your private VPC subnets while allowing necessary inbound traffic.

## 4. Setup Checklist

1. Deploy a standard Ubuntu 22.04 LTS instance from an official image. Do **not** pre-install scenario packages beforehand.
2. Verify SSH root or sudo access on port 22.
3. Verify that AppArmor is enabled:
   ```bash
   sudo aa-status
   ```
4. Copy the bootstrap script and execute it on the guest:
   ```bash
   scp ops/bootstrap-node.sh <admin>@<vm-ip>:/tmp/
   ssh <admin>@<vm-ip> 'sudo WETWARE_VM_IP=<vm-ip> bash /tmp/bootstrap-node.sh'
   ```
5. From your local development machine, run the deploy script:
   ```bash
   ./ops/deploy.sh
   ```
6. Take a hypervisor snapshot of this clean state for instant rollbacks.
