# vobot-gpu-daemon

Tiny Python stdlib-only HTTP daemon that reads the local GPU tooling
(`nvidia-smi` or `amd-smi`) on whatever host it runs on and serves the numbers
as JSON, so the Vobot Mini Dock `nvtop` app has something to poll. No
dependency on any third-party dashboard (e.g. gpu-hot) — this is our own
service so the app works for anyone with a GPU and this daemon installed, not
just this specific homelab.

Response schema intentionally matches gpu-hot's `/api/gpu-data` shape, so the
on-device app's parser is backend-agnostic — point its `server` setting at
this daemon or at a gpu-hot instance interchangeably.

Currently deployed on: **proxmox host** (NVIDIA RTX 5060 Ti, bare metal) and
**EVO-X2** (AMD Radeon 8060S APU, `192.168.1.152`). The design makes no
assumption about either — it just shells out to whatever vendor CLI resolves
locally, so it works the same way in an LXC/VM with GPU passthrough.
macOS/Windows equivalents are a future, out-of-scope idea.

## Vendor backends

Detected automatically at startup: `nvidia-smi` on PATH wins, else `amd-smi`.
Override with the `VOBOT_GPU_BACKEND` env var (`nvidia` or `amd`) on a host
that has both. The active backend is reported in every response as `backend`.

AMD numbers come from `amd-smi monitor` (per-poll) plus a one-time cached
`amd-smi static` / `amd-smi list` for board identity and clock/PCIe ceilings,
and `amd-smi process` for the process table. Some fields simply don't exist on
every AMD part — APUs like the 8060S report no fan, no PCIe link state, no
performance state, and no power limit, so those come back `null`/`""`. The app
already treats every field as optional, so this renders fine. Note that on an
APU the reported VRAM is GTT (shared system memory), which is why totals look
large (e.g. 78 GB) compared to the small dedicated carveout.

The AMD process table is also frequently empty: verified on the 8060S that
`amd-smi process` reports "No running processes detected" even at 90% GPU
utilization and even when run as root, so the app's Processes page will be
blank there. That's an amd-smi/KFD reporting gap on APUs, not a daemon bug \u2014
the parsing is in place and will populate on parts that do report.

## Endpoints

- `GET /api/gpu-data` — `{"gpus": {"0": {...}}, "processes": {...}, "timestamp": <unix ts>, "backend": "nvidia"|"amd", "version": "<x.y.z>", "git_commit": "<short sha>"}`
- `GET /health` — `{"status": "ok", "backend": ..., "version": ..., "git_commit": "<short sha>"}`

## Versioning

`VERSION` at the top of `vobot_gpu_daemon.py` is the daemon's own semver, and
it's reported in every response (and in the `Server` header). Bump it on any
response-schema or backend-behaviour change — it's the field the app can
feature-test against, whereas `git_commit` only answers "is this the code I
just pushed?". The app's Details page shows both, plus the active backend.

- **1.1.0** — `amd-smi` backend + auto-detection; added `backend` and `version`
  response fields.
- **1.0.0** — `nvidia-smi` only.

Every response includes `git_commit` — the short git SHA of the code that's
actually running, stamped in at deploy time (see below). Compare it against
`git rev-parse --short HEAD` locally to confirm the daemon isn't stale before
chasing a "bug" that's really just an un-deployed fix. A `-dirty` suffix means
the deployed file didn't match the last commit when it was pushed out.

## Deploy (systemd, Debian/Proxmox host)

Start from within this directory: `cd ./nvtop-daemon`

**Windows (PowerShell)** — uses the OpenSSH client built into Windows 11 for `ssh`/`scp`:
```powershell
$Server = "proxmox"
$SshTarget = "root@$Server"
$ApiUrl = "http://$Server.home.lan:8039/api/gpu-data"

$GitHash = git rev-parse --short HEAD
git diff --quiet -- vobot_gpu_daemon.py
if ($LASTEXITCODE -ne 0) { $GitHash = "$GitHash-dirty" }
$Stamped = Join-Path $env:TEMP 'vobot_gpu_daemon.stamped.py'
(Get-Content vobot_gpu_daemon.py -Raw) -replace '(?m)^GIT_COMMIT = .*', "GIT_COMMIT = `"$GitHash`"" |
    Set-Content -Path $Stamped -NoNewline -Encoding utf8

ssh $SshTarget "mkdir -p /opt/vobot-gpu-daemon"
scp $Stamped "${SshTarget}:/opt/vobot-gpu-daemon/vobot_gpu_daemon.py"
scp vobot-gpu-daemon.service "${SshTarget}:/etc/systemd/system/"
ssh $SshTarget "systemctl daemon-reload && systemctl enable --now vobot-gpu-daemon && systemctl restart vobot-gpu-daemon"
curl $ApiUrl
```

**Non-root SSH target** (e.g. `evox2`, where you log in as a normal user with
passwordless sudo): stage through `/tmp` first, since `scp` can't write to
`/opt` or `/etc` unprivileged.
```powershell
scp $Stamped evox2:/tmp/vobot_gpu_daemon.py
scp vobot-gpu-daemon.service evox2:/tmp/
ssh evox2 "sudo mkdir -p /opt/vobot-gpu-daemon && sudo cp /tmp/vobot_gpu_daemon.py /opt/vobot-gpu-daemon/ && sudo cp /tmp/vobot-gpu-daemon.service /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl enable --now vobot-gpu-daemon && sudo systemctl restart vobot-gpu-daemon"
curl http://192.168.1.152:8039/api/gpu-data
```

**Linux/macOS (bash)**:
```bash
SERVER="proxmox"
SSH_TARGET="root@$SERVER"
API_URL="http://${SERVER}.home.lan:8039/api/gpu-data"

GIT_HASH=$(git rev-parse --short HEAD)$(git diff --quiet -- vobot_gpu_daemon.py || echo -dirty)
sed "s/^GIT_COMMIT = .*/GIT_COMMIT = \"$GIT_HASH\"/" vobot_gpu_daemon.py > /tmp/vobot_gpu_daemon.stamped.py

ssh "$SSH_TARGET" "mkdir -p /opt/vobot-gpu-daemon"
scp /tmp/vobot_gpu_daemon.stamped.py "$SSH_TARGET:/opt/vobot-gpu-daemon/vobot_gpu_daemon.py"
scp vobot-gpu-daemon.service "$SSH_TARGET:/etc/systemd/system/"
ssh "$SSH_TARGET" "systemctl daemon-reload && systemctl enable --now vobot-gpu-daemon && systemctl restart vobot-gpu-daemon"
curl "$API_URL"
```

`systemctl restart` is not redundant next to `enable --now`: `--now` only
*starts* the unit if it's stopped, so on an already-running host it would
happily leave the old code in memory and you'd chase a phantom "my fix didn't
deploy" bug — check `git_commit` in the response if in doubt.

`systemctl enable --now` both starts the service immediately (equivalent to the old
`restart`) and symlinks it into `multi-user.target.wants/`, which is what actually makes
it survive a reboot — `WantedBy=multi-user.target` in the unit file alone does nothing
until `enable` is run at least once. It's idempotent, so leaving it in every deploy is
harmless and self-healing if someone ever disables the unit by hand.

`Restart=always` (rather than `on-failure`) covers crashes *and* any clean-exit case
(e.g. an uncaught exception that still returns 0, or someone fat-fingering a manual
`kill` without `stop`) — for a daemon that should just always be up, `always` is the
safer default. `StartLimitIntervalSec=60` / `StartLimitBurst=5` in `[Unit]` caps it at 5
restarts per 60s; if `vobot_gpu_daemon.py` is crash-looping (e.g. `nvidia-smi` missing),
systemd gives up and marks the unit `failed` instead of burning CPU in a restart storm —
check with `systemctl status vobot-gpu-daemon` if `/api/gpu-data` ever goes dark.

Runs as `nobody` — `/dev/nvidia*` (NVIDIA) and `/dev/kfd` + `/dev/dri/render*`
(AMD) are world read/write on these hosts, so no elevated privileges are
needed to query the GPU.

To restart it manually

```bash
ssh root@proxmox "systemctl daemon-reload && systemctl restart vobot-gpu-daemon"
```

## Config

No config file. `PORT` (default `8039`) is at the top of
`vobot_gpu_daemon.py`; `VOBOT_GPU_BACKEND` (`nvidia`/`amd`) forces the vendor
backend if auto-detection picks wrong. Multi-GPU hosts are handled
automatically (`gpus` dict gets one entry per GPU index); nothing to change.
