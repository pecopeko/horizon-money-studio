# SLSA Provenance, OpenVEX & Build-Install Supply-Chain Security Auditor (`cicd-slsa-vex-provenance-auditor`)

Deterministic Pay-Per-Event (`provenance_audited` @ `$0.003`) supply-chain security auditor detecting:
- `SLSA-PIPE-01`: Pipe-to-shell remote installers (`curl ... | bash/sh`, `wget ... | sh`, `iwr ... | iex`)
- `SLSA-NPM-HOOK-02`: Package lifecycle hooks (`preinstall`/`postinstall`/`prepare`) spawning `curl`/`wget`/`bash`/`sh -c`/`powershell`/`node -e`
- `SLSA-SIG-03`: Disabled signature, provenance, or checksum verification (`verify_sig: false`, `--no-verify`, `provenance: false`)
- `SLSA-TAG-04`: Mutable floating release references (`@main`, `@master`, `:latest`)
- `SLSA-LVL-05`: Unpinned source digest or level-0 SLSA predicate (`source_digest: null`, `slsa_level: 0`)
- `SLSA-VEX-06`: OpenVEX `"not_affected"` assertion lacking a mandatory `justification`
