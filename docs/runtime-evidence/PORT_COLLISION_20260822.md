# PostgreSQL host-port collision evidence

Captured: 2026-08-23T04:32:33+00:00 UTC
Task: `t_5c1d1456`
Tmux pane: `0:7.0`

## Finding

The host's `0.0.0.0:5432` is already occupied by the rootless Podman port-forward process for the existing `db-postgres` container. A new rootless container attempting to publish `0.0.0.0:5432` fails before PostgreSQL starts:

```
Error: pasta failed with exit code 1:
Listen failed for HOST TCP port 0.0.0.0/5432: Address already in use
Couldn't listen on requested ports
```

The reproduction command returned exit status `126`:

```
podman run --pull=never --name trade-port-collision-evidence-20260822 \
  -p 0.0.0.0:5432:5432 docker.io/library/postgres:15-alpine
```

No image build, CMake build, or C++ test was run. `--pull=never` ensured the reproduction did not fetch an image.

## Ownership evidence

Timestamp: 2026-08-22T23:30:18-05:00 (`2026-08-23T04:30:18Z`)

Command:

```
ss -ltnp '( sport = :5432 )'
```

Output:

```
LISTEN 0 4096 *:5432 *:* users:(("rootlessport",pid=2669789,fd=11))
```

Command:

```
ps -o pid,ppid,user,etime,cmd -p 2669789
```

Output:

```
PID     PPID    USER   ELAPSED   CMD
2669789 2669733 kahlil 05:56:14  rootlessport
```

Command:

```
podman ps --all --format 'table {{.ID}}\t{{.Names}}\t{{.Status}}\t{{.Ports}}\t{{.Image}}'
```

Relevant output:

```
9ab627e64ce7 db-postgres Up 6 hours (healthy) 0.0.0.0:5432->5432/tcp docker.io/library/postgres:16.8
b602fc4bbb34 trade_db_1 Up 54 minutes (healthy) 0.0.0.0:5433->5432/tcp docker.io/library/postgres:15-alpine
```

The `db-postgres` inspection reported:

```
name=db-postgres id=9ab627e64ce716b9ed0837e4598d87a3e568c7dd9cb8f5d9d433a29412331307
status=running started=2026-08-22 17:34:21.18728879 -0500 CDT
ports={"5432/tcp":[{"HostIp":"0.0.0.0","HostPort":"5432"}]}
network=db_prdnet ip=10.89.0.42
```

The trade database inspection reported:

```
name=trade_db_1 id=b602fc4bbb34fc164849d5ba8be392910efd087b8511d1a7c47bd3f44ad295cd
status=running started=2026-08-22 22:35:23.603101715 -0500 CDT
ports={"5432/tcp":[{"HostIp":"0.0.0.0","HostPort":"5433"}]}
network=trade_trading-network ip=10.89.1.3
```

## Host versus internal network contract

The two port numbers are not contradictory:

- `0.0.0.0:5432` is a host-side published binding. It is owned by the separate `db-postgres` container through `rootlessport`.
- The trade stack publishes its container port `5432` on host port `5433` (`5433:5432`), avoiding that collision.
- Trade services communicate over `trade_trading-network` using the service DNS name `db` and container port `5432` (`db:5432`). This path does not traverse the host's published port and must remain unchanged.
- The repo-local `docker-compose.yml` explicitly documents this distinction and uses `${POSTGRES_HOST_PORT:-5433}:5432`.

## Tmux evidence and stale-container condition

The latest full capture of pane `0:7.0` was saved during investigation to `/tmp/trade-pane-070.txt` (5,426 lines). Its current tail shows healthy trade/DB activity; the historical bind-failure line is no longer in the pane scrollback. The existing reproduction log `/tmp/trade-compose-repro-20260822.txt` records the attempted command `POSTGRES_HOST_PORT=5432 timeout 45s podman-compose up --no-build` at `2026-08-22T23:09:11.443869-05:00`, which returned `124`, but that log did not preserve the rootlessport stderr line. Therefore the rootlessport-specific evidence is preserved here via the fresh equivalent bind reproduction and the live `ss` owner correlation, while the pane limitation is explicit.

The failed reproduction left a created, non-running container because the command intentionally omitted `--rm` to avoid hidden cleanup:

```
podman ps -a --filter name=trade-port-collision-evidence-20260822
id=718a3a55e04f name=trade-port-collision-evidence-20260822 status=Created ports=0.0.0.0:5432->5432/tcp image=docker.io/library/postgres:15-alpine
```

This is a stale-container cleanup item for later closeout. It was not removed during evidence capture.
