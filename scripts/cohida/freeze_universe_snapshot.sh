#!/usr/bin/env bash
# Reads the distinct set of symbols already ingested into cohida's
# granularity tables (crypto_300, crypto_900, crypto_3600, crypto_21600,
# crypto_86400 -- the bare `crypto` table is present in schema but unused)
# and emits a versioned, hashed membership snapshot. See
# contracts/cohida/provider_universe_manifest.md for the schema and the
# reasoning behind why this freeze is needed.
#
# Read-only: runs SELECT DISTINCT queries only. Never writes to the source
# database.
set -euo pipefail

HOST=""
PORT="5432"
DB=""
USER_NAME=""
SCHEMA="priority_queue"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host) HOST="$2"; shift 2 ;;
    --port) PORT="$2"; shift 2 ;;
    --db) DB="$2"; shift 2 ;;
    --user) USER_NAME="$2"; shift 2 ;;
    --schema) SCHEMA="$2"; shift 2 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

if [[ -z "$HOST" || -z "$DB" || -z "$USER_NAME" ]]; then
  echo "usage: $0 --host <host> [--port 5432] --db <dbname> --user <readonly-user> [--schema priority_queue]" >&2
  echo "(PGPASSWORD env var, or ~/.pgpass, supplies the password; never pass it as an argument)" >&2
  exit 2
fi

CONN="host=${HOST} port=${PORT} dbname=${DB} user=${USER_NAME} sslmode=prefer options=--default-transaction-read-only=on"

SYMBOLS_RAW=$(psql "$CONN" -X -A -t -c "
  SELECT DISTINCT symbol FROM ${SCHEMA}.crypto_300
  UNION SELECT DISTINCT symbol FROM ${SCHEMA}.crypto_900
  UNION SELECT DISTINCT symbol FROM ${SCHEMA}.crypto_3600
  UNION SELECT DISTINCT symbol FROM ${SCHEMA}.crypto_21600
  UNION SELECT DISTINCT symbol FROM ${SCHEMA}.crypto_86400;
")

EARLIEST_LATEST=$(psql "$CONN" -X -A -t -F'|' -c "
  SELECT min(timestamp), max(timestamp) FROM ${SCHEMA}.crypto_300;
")
EARLIEST_BAR=$(echo "$EARLIEST_LATEST" | cut -d'|' -f1)
LATEST_BAR=$(echo "$EARLIEST_LATEST" | cut -d'|' -f2)

SYMBOLS_JSON=$(printf '%s\n' "$SYMBOLS_RAW" | awk 'NF' | python3 -c '
import json, sys
symbols = [line.strip() for line in sys.stdin if line.strip()]
print(json.dumps(sorted(set(symbols))))
')

MEMBERSHIP_SHA256=$(printf '%s' "$SYMBOLS_JSON" | sha256sum | cut -d" " -f1)
GENERATED_AT_UTC=$(date -u +%Y-%m-%dT%H:%M:%SZ)

python3 - "$SYMBOLS_JSON" "$MEMBERSHIP_SHA256" "$GENERATED_AT_UTC" "$EARLIEST_BAR" "$LATEST_BAR" <<'PY'
import json, sys, datetime
symbols_json, membership_sha256, generated_at_utc, earliest_bar, latest_bar = sys.argv[1:6]
symbols = json.loads(symbols_json)

def to_iso(ts):
    ts = ts.strip()
    if not ts:
        return None
    dt = datetime.datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

latest_iso = to_iso(latest_bar)
staleness = None
if latest_iso:
    latest_dt = datetime.datetime.strptime(latest_iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)
    now_dt = datetime.datetime.now(datetime.timezone.utc)
    staleness = int((now_dt - latest_dt).total_seconds())

snapshot = {
    "universe_version": "v1",
    "generated_at_utc": generated_at_utc,
    "provider": "coinbase",
    "source": "cohida-db-prod (UNION DISTINCT symbol across crypto_300, crypto_900, crypto_3600, crypto_21600, crypto_86400)",
    "observed_coverage_window_utc": {
        "earliest_bar": to_iso(earliest_bar),
        "latest_bar": latest_iso,
        "snapshot_taken_at": generated_at_utc,
        "staleness_at_snapshot_seconds": staleness,
    },
    "membership_sha256": membership_sha256,
    "symbol_count": len(symbols),
    "symbols": symbols,
    "effective_from_utc": generated_at_utc,
    "effective_to_utc": None,
    "id_mapping": "identity -- the stored symbol column IS the Coinbase product ID",
    "venue": "coinbase",
    "quote_base_convention": "Coinbase product ID format BASE-QUOTE (e.g. BTC-USD)",
    "granularities_seconds": [300, 900, 3600, 21600, 86400],
    "revision_policy": "NOT append-only -- verified via DatabaseManager.cpp: INSERT ... ON CONFLICT (symbol, timestamp) DO UPDATE overwrites open/high/low/close/volume and updated_at in place on every re-retrieval, with no history of the prior value retained. created_at is set once (DB default, never in the UPDATE SET clause); updated_at > created_at is the only available signal that a bar has been revised since first ingestion.",
    "freshness_policy": "Fresh if latest bar (any granularity) is within 30h of now (24h daily-retrieval cycle + 6h buffer). Beyond 30h, treat as a failed/missed run and fail-closed rather than compute against stale candles.",
}
print(json.dumps(snapshot, indent=2))
PY
