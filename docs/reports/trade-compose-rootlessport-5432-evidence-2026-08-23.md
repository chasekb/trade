# Rootlessport host-port collision evidence

Captured at: `2026-08-23T06:49:42Z` (UTC)
Repository: `trade`
Pane: `0:7.0` (`session=0`, `window=7`, `pane=0`, tmux pane id `%22`)

## Existing collision evidence

The previously captured runtime evidence is preserved in
`docs/reports/trade-compose-runtime-triage-2026-08-21.md`. Its scope and exact
startup command were:

```text
TAG=dev podman-compose up --no-build
```

The relevant stderr/stdout recorded there is:

```text
[db] | Error: unable to start container ...: rootlessport listen tcp 0.0.0.0:5432: bind: address already in use
```

The same report records that an existing `db-postgres` container owned host
port `5432`, while the failed attempt left `trade_db_1`,
`trade_cpp-backend_1`, and `trade_frontend_1` in `Created` state. The original
compose command's process exit status was not retained in the historical pane
capture and is therefore **unavailable**, not inferred.

## Current pane preservation capture

The pane was inspected without starting, stopping, or rebuilding containers.
Exact capture command:

```text
tmux capture-pane -p -t 0:7.0 -S -3000
```

The capture command exited with status `0`. The current pane did not reproduce
the `rootlessport`/`5432` bind failure; it contained later application and
shutdown output. Relevant current capture output includes:

```text
[db]          | 2026-08-23 05:37:55.323 UTC [1] LOG:  received fast shutdown request
[db]          | 2026-08-23 05:38:00.808 UTC [1] LOG:  database system is shut down
[redis]       | 1:M 23 Aug 2026 05:41:41.402 # Redis is now ready to exit, bye bye...
[kahlil@archbtw trade]$
```

Pane metadata was obtained with:

```text
tmux display-message -p -t 0:7.0 'session=#{session_name} window=#{window_index} pane=#{pane_index} pane_id=#{pane_id} current_command=#{pane_current_command} current_path=#{pane_current_path}'
```

It returned:

```text
session=0 window=7 pane=0 pane_id=%22 current_command=bash current_path=/run/media/unordered_map/priority_queue/log(perplexity)/-sum/log/Pr(context_for_token)/chasecapitalmanagement/etl/trade
```

## Separate stale-container observation

The historical collision report separately observed that the failed Compose
attempt left containers in `Created` state. That is cleanup/state residue, not
part of the rootlessport collision finding. The same report records that after
the host-port mapping repair, no trade containers remained in `Created` state.

## Safety and limitation

No Docker or Podman image build, CMake build, or C++ test was run. Reproduction
was not attempted because the current pane was already in a later runtime
state and deliberately preserving the existing collision evidence is safer
than inducing another host-port conflict. The collision finding is therefore
historical/preserved evidence, not a fresh reproduction at this timestamp.
