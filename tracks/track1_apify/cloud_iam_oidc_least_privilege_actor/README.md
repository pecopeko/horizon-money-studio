# Cloud IAM & OIDC Least-Privilege Auditor (`cloud-iam-oidc-least-privilege-auditor`)

Zero-API-key Python Pay-Per-Event (`iam_policy_audited` @ `$0.003`) Actor auditing Cloud IAM policies & OIDC Trust Federations:
- `IAM-WILD-01`: Wildcard admin (`Effect: Allow`, `Action: "*"` / `"*:*"`, `Resource: "*"`)
- `IAM-OIDC-02`: Overbroad GitHub OIDC `token.actions.githubusercontent.com` trust (missing `sub` or wildcard `repo:*/*` / `repo:org/*` without branch/env pinning)
- `IAM-PRIVESC-03`: Privilege escalation actions (`iam:PassRole`, `iam:CreatePolicyVersion`, `iam:AttachRolePolicy`, `iam:PutRolePolicy`, etc.) on wildcard `*`
- `IAM-TRUST-04`: Public cross-account `Principal: "*"` or `AWS: "*"` without `Condition`
- `IAM-NOTACTION-05`: `Effect: Allow` combined with `"NotAction"`
- `IAM-K8S-IRSA-06`: Kubernetes Workload Identity / IRSA `system:serviceaccount:*:*` wildcard
