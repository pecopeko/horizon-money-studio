# GraphQL Schema DoS & Introspection Security Auditor (`graphql-schema-dos-introspection-auditor`)

Deterministic Pay-Per-Event (`schema_audited` @ `$0.003`) auditor validating GraphQL SDL & server configuration against:
- `GQL-INTROSPECTION-01` (`high`): Exposed `introspection` / `graphiql` / `playground`
- `GQL-DEPTH-02` (`high`): Missing `depthLimit` / `maxDepth` on nested object references
- `GQL-BATCH-03` (`high`): Enabled query batching without `maxAliases` / `costLimit`
- `GQL-SENSITIVE-04` (`critical`): Unprotected credential/PII fields (`passwordHash`, `secretKey`, `myNumber`, etc.)
- `GQL-UNBOUNDED-LIST-05` (`medium`): Unbounded `Query` list fields without `first`/`limit`/`take`
- `GQL-CSRF-06` (`medium`): `csrfPrevention: false`
