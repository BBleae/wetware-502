# Security

This project intentionally behaves like a compromised production server and
exposes a SSH entry point that accepts any password/key for the *scenario*
account. Treat it as a honeypot, not as production software.

- Run it only on a **dedicated, disposable VM** you own.
- Do not expose the management SSH port or the hypervisor API to the tested
  agent.
- Keep `.local/` (real hosts, keys, reports) out of version control; it is
  gitignored.
- The session confinement (AppArmor + mount masking) is a detection/realism
  layer, not a security boundary against a malicious local root user.
- Report security issues privately to the maintainer instead of opening a
  public issue with exploit details.
