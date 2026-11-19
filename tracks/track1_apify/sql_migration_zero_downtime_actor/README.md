# PostgreSQL & MySQL Zero-Downtime Migration Lock Safety Auditor (`postgres-mysql-migration-lock-safety-auditor`)

Deterministic Pay-Per-Event (`migration_audited` @ `$0.003`) SQL migration CI/pre-deploy auditor catching:
- `SQL-LOCK-01` (`high`): `CREATE/DROP INDEX` without `CONCURRENTLY` on Postgres
- `SQL-TXN-02` (`critical`): `CONCURRENTLY` inside explicit `BEGIN` / `START TRANSACTION`
- `SQL-TYPE-03` (`high`): `ALTER COLUMN ... TYPE` / `MODIFY COLUMN` table rewrite lock
- `SQL-FK-04` (`medium`): `ADD CONSTRAINT ... FOREIGN KEY` missing `NOT VALID`
- `SQL-DESTRUCTIVE-05` (`high`): `DROP TABLE` / `DROP COLUMN` / `TRUNCATE` without `-- safety-ack: allow-destructive`
- `SQL-UNBOUNDED-DML-06` (`high`): `UPDATE` or `DELETE FROM` without `WHERE`
- `SQL-TIMEOUT-07` (`low`): `ALTER TABLE` omitting `lock_timeout`
