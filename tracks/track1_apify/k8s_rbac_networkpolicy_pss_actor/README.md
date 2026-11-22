# Kubernetes RBAC, NetworkPolicy Zero-Trust & PodSecurity Auditor

Pay-Per-Event (`cluster_policy_audited` @ `$0.003`) Apify Actor screening Kubernetes manifests across 6 security controls:
- `K8S-RBAC-01`: Wildcard `verbs`/`resources` or `cluster-admin` RoleRef bindings
- `K8S-SA-02`: `automountServiceAccountToken: true` credential exposure
- `K8S-NETPOL-03`: Wide-open `0.0.0.0/0` without `except` or allow-all `podSelector: {}`
- `K8S-PSS-04`: Weak Pod Security Standards (`privileged`/`baseline` or `seccompProfile: Unconfined`)
- `K8S-WEBHOOK-05`: Admission webhook fail-open (`failurePolicy: Ignore`)
- `K8S-QUOTA-06`: Missing or unlimited container resource quotas (`limits: null` / `unlimited`)
