# Dockerfile, Docker Compose & Kubernetes Hardening Auditor

Pay-Per-Event Apify Actor (`$0.003` per `manifest_audited`) scanning container definitions deterministically for critical misconfigurations:

- `CNT-LATEST-TAG`: `FROM` or `image:` using `:latest` or omitting an explicit tag/digest.
- `CNT-ROOT-USER`: `Dockerfile` lacking a non-root `USER` instruction (or ending at `USER root`/`0`), or K8s Pod/Deployment lacking `runAsNonRoot: true`.
- `CNT-SECRET-IN-ENV-ARG`: `ENV`/`ARG` or YAML env assignments embedding literal secrets (`PASSWORD`, `SECRET`, `API_KEY`, `PRIVATE_KEY`, `ACCESS_KEY`, `AUTH_TOKEN`).
- `CNT-PRIVILEGED-HOST`: `privileged: true`, `network_mode: host`, `hostNetwork: true`, `hostPID: true`, or mounting `/var/run/docker.sock`.
- `CNT-REMOTE-EXEC-ADD`: Remote tarball/script fetching via `ADD https://...` or piping `curl|sh` / `wget|bash`.
