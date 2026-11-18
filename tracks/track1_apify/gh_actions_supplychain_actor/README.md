# GitHub Actions Workflow Supply-Chain Security Auditor

Pay-Per-Event Apify Actor (`$0.003` per `workflow_audited`) that deterministically audits `.github/workflows/*.yml` files for high-impact CI supply-chain risks:

- `GHA-UNPINNED-ACTION`: Third-party `uses: owner/repo@ref` not pinned to an immutable 40-char commit SHA (`actions/*` and `github/*` official actions exempted).
- `GHA-PRT-UNTRUSTED-CHECKOUT`: `pull_request_target` workflows checking out `github.event.pull_request.head` / `github.head_ref`.
- `GHA-SCRIPT-INJECTION`: Untrusted `${{ github.event.* }}` PR/issue/comment title/body/head_ref interpolation directly inside `run:` shell commands.
- `GHA-EXCESSIVE-PERMISSIONS`: `permissions: write-all` or missing least-privilege `permissions:` block.
- `GHA-CURL-PIPE-SH`: Remote installer piping (`curl ... | sh` or `wget ... | bash`).
