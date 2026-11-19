# Terraform HCL Security & FinOps Governance Auditor

Pay-Per-Event Apify Actor (`$0.003` per `module_audited`) scanning Terraform `.tf` HCL modules deterministically for common cloud security and FinOps governance risks:

- `TF-PUBLIC-STORAGE`: Public storage ACLs (`public-read`/`public-read-write`), `block_public_acls = false`, or GCP `allUsers`/`allAuthenticatedUsers`.
- `TF-OPEN-INGRESS-0000`: Unrestricted `0.0.0.0/0` or `::/0` ingress on sensitive admin/DB ports (`22`, `3389`, `3306`, `5432`, `6379`, `27017`) or `from_port = 0`.
- `TF-UNENCRYPTED-DATA`: `storage_encrypted = false` or `encrypted = false`.
- `TF-WILDCARD-IAM`: IAM `Allow` statements pairing wildcard actions (`"*"` / `"*:*"`) with `"*"` resources.
- `TF-HARDCODED-SECRET`: Literal non-variable credentials assigned to `access_key`, `secret_key`, `password`, `api_key`, or `private_key`.
- `TF-MISSING-FINOPS-TAGS`: Billable compute/RDS/NAT/EKS resources missing `tags` maps.
