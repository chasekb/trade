# Cohida provider universe manifest

Owning task: `t_27acce22` (P2 read-only signal and intent-outcome normalization), gated on
`t_25ac3ce2` (P1 cohida evidence and source-contract intake).

## Status: sanctioned universe snapshot exists (v1)

P1 previously came back `FAIL_CLOSED` / `UNKNOWN_REMEDIATE` because no sanctioned, versioned,
hashed provider-universe membership snapshot had ever existed for cohida, anywhere in this
system's evidence history — confirmed by inspecting every prior read-only evidence artifact
(`cohida_evidence_manifest_2026-09-19.json`, the P1 `input-manifest.json`/
`validation-reconciliation.json`). This was not a missing sign-off from a separate "ETL
owner" and "data-quality owner" role — on this project those are the same person, the
repository owner — it was a real, never-before-taken action.

That action has now been taken. `contracts/cohida/universe_snapshot_v1.json` (committed
alongside this document) is a real, read-only observation of `cohida-db-prod`'s actual
ingested history, not a fabricated or inferred value.

## What is known (evidence-backed)

- **Provider**: Coinbase. `cpp-cohida/src/api/CoinbaseClient.cpp` and
  `legacy_python/src/coinbase_client.py` are the only data-source integrations in the cohida
  codebase; `cohida symbols --list` calls `CoinbaseClient::get_available_symbols()` directly
  against Coinbase's product listing.
- **Symbol identity / mapping**: cohida stores the Coinbase product ID directly as `symbol`
  (e.g. `BTC-USD`) with no intermediate mapping table. Coinbase's own product ID **is** the
  canonical identity; there is no separate provider-native-ID-to-symbol mapping step.
- **Venue / quote currency**: Coinbase spot. Quote currencies observed in the snapshot:
  USD, USDC, USDT, EUR, GBP, BTC, ETH, INR, AUD, BRL, CAD, SGD (multi-quote pairs exist, e.g.
  `BTC-EUR`, `ETH-BTC` — not exclusively `-USD`).
- **Granularities retrieved**: 300s, 900s, 3600s, 21600s, 86400s (one table per granularity:
  `crypto_300`, `crypto_900`, `crypto_3600`, `crypto_21600`, `crypto_86400`); the bare
  `crypto` table is present in schema but unused (0 rows).
- **Timestamp semantics**: `timestamp without time zone`, database session UTC.
- **Membership** (this snapshot, taken 2026-09-23 against the real production data volume):
  **949 distinct symbols**, union of `DISTINCT symbol` across all five granularity tables.
  `membership_sha256` in the snapshot file is the canonical hash of that sorted, deduplicated
  list.
- **Observed coverage window**: earliest bar 2017-07-14T23:55:00Z, latest bar
  2026-09-19T06:50:00Z (5-minute granularity). At snapshot time (2026-09-23T03:06Z) the most
  recent ingested bar was **~3.9 days old** — retrieval had not run in the intervening days.
  This is a real, disclosed staleness observation, not a pass/fail judgment (see freshness
  policy below).

## How the snapshot was produced

`scripts/cohida/freeze_universe_snapshot.sh` (committed alongside this document) runs
`SELECT DISTINCT symbol FROM crypto` in a read-only transaction and emits the schema below.
For this v1 snapshot, the equivalent query was run manually against all five granularity
tables (the bare `crypto` table is unused/empty) since the schema splits data by granularity
rather than keeping one canonical table; a follow-up should either point the script at the
granularity tables directly or add a canonicalizing view, whichever the cohida repo owner
prefers — noted as a small implementation cleanup, not a blocker.

The `cohida-db-prod` container was started read-only-intent (no schema/data writes performed)
against its existing production data volume
(`etl/cohida/postgres-data` → `/var/lib/postgresql/data`) to take this observation, and left
running per explicit instruction.

## Snapshot schema

See `contracts/cohida/universe_snapshot_v1.json` for the full committed snapshot. Fields:
`universe_version`, `generated_at_utc`, `provider`, `source`,
`observed_coverage_window_utc` (`earliest_bar`, `latest_bar`, `snapshot_taken_at`,
`staleness_at_snapshot_seconds`), `membership_sha256`, `symbol_count`, `symbols` (sorted
array), `effective_from_utc`, `effective_to_utc` (null until superseded),
`id_mapping`, `venue`, `quote_base_convention`, `granularities_seconds`, `revision_policy`.

## Freshness policy

Cohida's retrieval (`scripts/retrieve-production.sh`) runs once daily at 00:00 UTC and pulls
**all five granularities in the same pass** (`cohida symbols --list | xargs ... retrieve-all
-g <granularity>` per granularity, one run). This is not a case of independently-cadenced
granularities needing independently-tuned thresholds — it collapses to one question: did
today's 00:00 UTC run actually succeed?

**Policy: data is fresh if the latest bar (any granularity) is within 30h of now** (24h
refresh cycle + 6h buffer for run duration/retry). Beyond 30h, the run is presumed to have
failed or not fired, and any consumer (P2 normalization, a strategy signal) must fail-closed
on that table rather than compute against stale candles.

This snapshot observed **~92 hours of staleness** (latest bar 2026-09-19T06:50Z, snapshot
taken 2026-09-23T03:06Z) — roughly four missed daily cycles. That is a live operational
failure of the daily retrieval job, not a manifest question, and is being tracked as an
incident on the `cohida` Kanban board rather than resolved here; see that board for the
current investigation.

## Revision/correction policy

Verified against the actual ingestion code (`cpp-cohida/src/database/DatabaseManager.cpp`),
not assumed. Cohida's retrieval is **not append-only**:

```sql
INSERT INTO ... (symbol, timestamp, open_price, high_price, low_price, close_price, volume, updated_at)
VALUES (...)
ON CONFLICT (symbol, timestamp) DO UPDATE SET
    open_price = EXCLUDED.open_price, high_price = EXCLUDED.high_price,
    low_price = EXCLUDED.low_price, close_price = EXCLUDED.close_price,
    volume = EXCLUDED.volume, updated_at = EXCLUDED.updated_at
```

Every write is an upsert keyed on `(symbol, timestamp)`. If the same bar is retrieved twice
— a retry, a backfill re-run, or Coinbase correcting a historical candle — its OHLCV values
are silently overwritten in place. No history of the prior value is retained anywhere.
`created_at` (schema default `CURRENT_TIMESTAMP`, set once, never in the `UPDATE SET` clause)
marks first ingestion; `updated_at` is rewritten on every insert **and** every conflict-update,
so `updated_at > created_at` is the only available signal that a bar has been revised at
least once since first ingestion — there is no record of what the prior value was.

**Consequence for P2 and downstream consumers:** a row read today is not guaranteed to read
the same on a later re-query. Anything that must be reproducible (a backtest, a signal
computed from a specific bar) must either (a) treat a row where `updated_at` has since
advanced past the computation time as invalidated and re-validate, or (b) snapshot the exact
row values used at computation time rather than re-deriving by `(symbol, timestamp)` lookup
later. This is a hard requirement for P2's design, not an optional nicety — silently trusting
`(symbol, timestamp)` as a stable key would violate the crypto evidence contract's
`correction_revision_semantics` provenance requirement.

## What's left

Both policy questions above are now answered with evidence, not assumption. P1 (`t_25ac3ce2`)
should be rerun against this manifest to attempt PASS; a PASS unblocks P2 (`t_27acce22`) to
proceed with real, non-fabricated universe identity and a documented, code-verified revision
model. The only remaining open item is operational, not evidentiary: cohida's daily retrieval
job needs to actually be fixed and start succeeding again.
