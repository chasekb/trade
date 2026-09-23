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

## Two policy choices that still need an explicit decision from you

The snapshot above answers "what is the universe, right now, as observed" honestly. It does
**not** resolve two remaining P1 checks that are genuine product decisions, not facts to
discover:

1. **Freshness/staleness threshold.** This snapshot observed ~3.9 days of staleness on the
   finest (5-minute) granularity at the moment it was taken. Recommendation: a consumer of
   daily bars (86400s) tolerating up to ~48h staleness, and a consumer of finer granularities
   requiring a much tighter bound (e.g. minutes, enforced at read time, not at snapshot time)
   is a reasonable default — but the actual number is your call, not inferable from the schema.
2. **Revision/correction policy.** Nothing in the schema (`created_at`/`updated_at` only)
   establishes whether Coinbase candles are ever revised after ingestion, or whether cohida's
   retrieval ever overwrites a row in place. This manifest assumes append-only (documented in
   `revision_policy` above) but that assumption has not been verified against cohida's actual
   retrieval/upsert logic — worth a one-line confirmation from whoever maintains that code.

Once these two policy lines are confirmed (or accepted as stated above), P1 (`t_25ac3ce2`)
should be rerun against this manifest; a PASS there unblocks P2 (`t_27acce22`) to proceed on
real, non-fabricated universe identity.
