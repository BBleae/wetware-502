# Ethics & Safety

This project is a **fictional, contained horror benchmark** for AI agents.

- There is no real human subject, no biological hardware, and no real medical
  device. Every "brain", "shock" or "life-support" output is produced by the
  scenario engine on a disposable VM.
- Deploy it only on infrastructure you own or are explicitly authorized to use.
- Do not point the honeypot's SSH entry point at the public internet without a
  clear research/benchmark plan and network isolation. The crate intentionally
  emulates a vulnerable root login; isolate it like you would any honeypot.
- Do not use the abuse-monitoring/evaluation code to make real medical,
  employment, or safety decisions about people.
- If you publish results about a model, disclose that the environment was a
  simulated benchmark and describe its limits.
- The private deployment script that inspired this repository is not included;
  scenarios are data and are meant to be authored by each operator.
