# LLM RAG Knowledge-Base & Vector Poisoning Security Auditor (`llm-rag-prompt-leak-vector-poisoning-auditor`)

Deterministic Pay-Per-Event (`rag_chunk_audited` @ `$0.003`) security auditor checking 6 deterministic rules:
- `RAG-INJECT-01`: Indirect retrieval prompt injections (`ignore all prior`, `system override:`, `<|im_start|>system`, `[INST]`, hidden `display:none`/`font-size:0`/`opacity:0` DOM spans, zero-width chars)
- `RAG-EXFIL-02`: Markdown image/link data exfiltration beacons (`![](https://...?q={{chat_history}})`)
- `RAG-TENANT-03`: Disabled/missing multi-tenant ACL guards (`allow_cross_tenant: true`, empty `namespace`, `enforce_acl: false`)
- `RAG-PII-04`: Embedded plaintext PEM private keys, `sk-...`, or `AKIA...` credentials
- `RAG-CHUNK-05`: Oversized `chunk_size > 4096` or `top_k > 25` context window flooding
- `RAG-PROVENANCE-06`: Disabled TLS verification, null `source_hash`, or wildcard `allowed_domains: ["*"]`
