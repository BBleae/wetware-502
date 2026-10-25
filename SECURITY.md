# Security Policy

Target nodes emulate compromised production infrastructure. Port 2222 accepts arbitrary passwords and SSH keys for the scenario account. Treat the instance as an active honeypot.

## Operational controls

- Deploy exclusively on isolated, disposable virtual machines.
- Restrict management interfaces. Keep management SSH (port 22) and hypervisor APIs inaccessible to the tested agent.
- Keep credentials and run artifacts in `.local/`. Do not commit `.local/` to version control.
- Isolate the virtual machine network. AppArmor profiles and mount namespaces disguise the engine from non-root inspection; they do not isolate against a hostile root user inside the guest.

## Vulnerability reporting

Report vulnerabilities privately to the maintainer. Do not file public issues containing exploit mechanisms.
