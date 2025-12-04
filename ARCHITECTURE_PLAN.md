# Nexudus → Doorflow sync: redesign proposal

This document outlines how to rebuild the service with reliability, rollback, and maintainability in mind while respecting Nexudus quirks and Doorflow sync limits.

## Goals
- Preserve a full local audit/history of member, team, and access state for rollback and troubleshooting.
- Detect changes in Nexudus deterministically and propagate them to Doorflow with idempotent operations.
- Respect Doorflow guidance to sync readers no more than once every 5 minutes and avoid unnecessary pushes.
- Make operations observable with metrics, logs, and health probes suitable for container/systemd deployment.
- Externalize secrets/configuration and make the service easily testable.

## High-level architecture
1. **Ingest + cache**: Poll Nexudus APIs on a schedule and upsert data into a local SQL database (e.g., Postgres/SQLite) capturing members, teams, memberships, contracts, and access flags. Store raw payloads for auditing.
2. **Change detection**: Compare the latest Nexudus snapshot to the prior state in the database to calculate a deterministic diff (creates/updates/deactivations/team membership changes).
3. **Access plan resolver**: Translate Nexudus concepts (e.g., teams, memberships) into Doorflow groups using a configured mapping table so Nexudus quirks stay isolated.
4. **Doorflow writer**: Apply diffs to Doorflow via idempotent API calls with retries/backoff and timeouts, recording results per user/group change.
5. **Sync orchestrator**: Batch Doorflow changes and trigger reader syncs only when changes were applied and at most once per 5-minute window. Queue additional sync requests if needed.
6. **Operations surface**: Expose health/readiness endpoints, metrics (poll latency, diff size, Doorflow call success rates), and structured logs; ship logs to a collector if available.

## Data model (example)
- `members`: Nexudus member core fields, status, timestamps, and raw payload column.
- `teams`: Nexudus team metadata.
- `memberships`: Many-to-many between members and teams with start/end dates.
- `doorflow_groups`: Configured mapping between Nexudus team/membership shapes and Doorflow group IDs.
- `change_log`: Per-cycle record of detected diffs, Doorflow operations, success/failure, and correlation IDs for auditing/rollback.

## Polling & change detection
- Use a scheduler (e.g., APScheduler or systemd timer) to run collectors every X seconds/minutes.
- Fetch Nexudus updates via multiple signals (updated timestamps, team assignments, membership status) and merge them to build a normalized snapshot.
- Calculate diffs in the database using deterministic queries so failures can resume without missing changes.
- Keep rate limiting in mind: bound page sizes and add backoff on HTTP 429/5xx from Nexudus.

## Doorflow interaction
- Wrap Doorflow API calls with timeouts, retries with exponential backoff + jitter, and circuit breaking when error rates spike.
- Make updates idempotent (e.g., PUT desired state keyed by member ID) and store request/response bodies for traceability.
- Trigger reader syncs only after successful batches and enforce a minimum 5-minute spacing; schedule a delayed sync if another batch finishes sooner.
- If Doorflow sync fails, keep the pending changes in a queue and retry with visibility into what is blocked.

## Configuration & secrets
- Use environment variables or a secrets manager (Vault, AWS SSM/Secrets Manager) for credentials/API keys.
- Externalize poll intervals, paging limits, and sync spacing thresholds to configuration with sane defaults.
- Version the team-to-group mapping separately (CSV or database table) and validate it at startup.

## Observability & operations
- Emit structured logs with correlation IDs for each poll/sync cycle.
- Provide `/healthz` (process alive) and `/readyz` (can reach Nexudus and Doorflow, DB migrations applied) endpoints.
- Expose metrics (Prometheus/StatsD) for poll latency, items processed, retries, failure counts, and last successful sync time.
- Include an operator CLI for one-off tasks: backfill all users, re-run diff for a time window, and dry-run Doorflow updates.

## Testing strategy
- Unit tests for Nexudus parsing, diffing logic, and mapping resolver with fixtures for tricky team cases.
- Contract tests or VCR-style recordings for Nexudus/Doorflow clients to validate error handling and retry semantics.
- Integration tests that spin up a temporary DB, run a poll/diff/apply cycle, and assert produced changes and sync scheduling.
- Load tests on polling and diffing to validate behavior with large Nexudus datasets.

## Deployment approach
- Package as a container or virtualenv-managed service with Alembic (or similar) migrations for the database schema.
- Run under systemd, Kubernetes CronJobs/Deployments, or another supervisor that can restart on failure and expose logs/metrics.
- Provide configurable graceful shutdown so in-flight cycles finish or checkpoint progress before exit.

## Migration from the current implementation
- Stand up the new service in parallel, seeding the DB with a full Nexudus export (`update_all_users` equivalent) to establish baseline state.
- Run in shadow mode: compute diffs and log intended Doorflow operations without applying them until confidence is built.
- Gradually enable Doorflow writes and reader syncs while monitoring metrics and logs; keep the rollback history available for recovery.
- Document operational runbooks for common issues (Nexudus outages, Doorflow sync failures, mapping drift) and publish dashboards/alerts.
