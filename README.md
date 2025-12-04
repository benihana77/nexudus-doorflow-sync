# Nexudus → Doorflow Sync (redesigned)

This branch contains a ground-up rebuild of the synchronisation service so that it:

- Polls Nexudus on a schedule and keeps a local SQL database of members, teams, and memberships for auditing and rollback.
- Computes deterministic diffs between the latest Nexudus snapshot and the previous state before updating Doorflow.
- Applies group mappings automatically by matching Nexudus team names to Doorflow group names, with an optional CSV override when needed.
- Triggers Doorflow reader syncs only when changes were applied and no more often than the configured interval.
- Exposes health and readiness endpoints and uses structured logging.

Run the service via the modern entrypoint `main.py`; legacy one-off scripts have been removed.

## Getting started

1. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

2. **Set required environment variables**

   - `NEXUDUS_USERNAME`
   - `NEXUDUS_PASSWORD`
   - `DOORFLOW_AUTH_KEY`
   - `DOORFLOW_SYSTEM_ID`

   Optional settings with sane defaults:

   - `DATABASE_URL` (default: `sqlite:///./nexudus_sync.db`)
   - `POLL_INTERVAL_SECONDS` (default: `60`)
   - `REQUEST_TIMEOUT_SECONDS` (default: `15`)
   - `MAX_HTTP_RETRIES` (default: `3`)
   - `DOORFLOW_SYNC_INTERVAL_SECONDS` (default: `300` seconds)
   - `NEXUDUS_PAGE_SIZE` (default: `200`)
   - `TEAM_MAPPING_PATH` (optional: path to a CSV override; defaults to automatic name-matching)
   - `LOG_LEVEL` (default: `INFO`)

3. **Run the service**

   ```bash
   python main.py
   ```

   The loop will poll Nexudus, persist snapshots, compute diffs, apply Doorflow updates, and schedule reader syncs when appropriate.

4. **Health endpoints**

   If you need HTTP health/readiness probes, you can run the Flask app defined in `sync_service.api.create_app` (e.g., via `flask --app sync_service.api:create_app run`). Endpoints:

   - `/healthz` – basic liveness
   - `/readyz` – verifies database connectivity

5. **Status dashboard**

   Run `python -m sync_service.status_app` (or `flask --app sync_service.status_app run --host 0.0.0.0 --port 8000`) to serve a minimal dashboard backed by the same database used by the sync loop. Environment options:

   - `DATABASE_URL` – points the UI at the correct database file or server
   - `STATUS_HOST` / `STATUS_PORT` – control bind host/port (defaults `0.0.0.0:8000`)
   - `LOG_LEVEL` – logging verbosity for the dashboard process

   The UI is available at `/` and includes a machine-readable `/status.json` endpoint.

## Key components

- `sync_service/config.py` – environment-driven configuration with sensible defaults and validation.
- `sync_service/clients/` – Nexudus and Doorflow API clients with retries and timeouts.
- `sync_service/db/models.py` – SQLAlchemy schema for members, teams, memberships, change logs, and sync state.
- `sync_service/change_detection.py` – deterministic diffing between stored state and the latest Nexudus snapshot.
- `sync_service/orchestrator.py` – orchestrates polling, persistence, diffing, Doorflow writes, and sync scheduling.
- `sync_service/team_mapping.py` – builds Nexudus-team → Doorflow-group mappings by name with optional CSV overrides.
- `sync_service/api.py` – minimal Flask app for health/readiness endpoints.

## Notes

- Doorflow advises syncing readers no more than once every five minutes. The `DOORFLOW_SYNC_INTERVAL_SECONDS` setting enforces this spacing.
- The change log table captures what updates were attempted, along with the Doorflow correlation ID when available, to aid troubleshooting and rollback.
- The service stores raw Nexudus payloads for each member, team, and membership to preserve full fidelity of the upstream data.
