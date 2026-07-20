# vobot-gpu-daemon

Tiny Python stdlib-only HTTP daemon that reads `nvidia-smi` on whatever host it
runs on and serves the numbers as JSON, so the Vobot Mini Dock `nvtop` app has
something to poll. No dependency on any third-party dashboard (e.g. gpu-hot) —
this is our own service so the app works for anyone with an NVIDIA GPU and this
daemon installed, not just this specific homelab.

Response schema intentionally matches gpu-hot's `/api/gpu-data` shape, so the
on-device app's parser is backend-agnostic — point its `server` setting at
this daemon or at a gpu-hot instance interchangeably.

Currently deployed on: **proxmox host itself** (bare metal, closest to the
GPU). The design makes no assumption about that — it just shells out to
whatever `nvidia-smi` resolves to locally, so it works the same way in an
LXC/VM with GPU passthrough. macOS/Windows equivalents are a future,
out-of-scope idea (would need a different data source than `nvidia-smi`).

## Endpoints

- `GET /api/gpu-data` — `{"gpus": {"0": {...}}, "processes": {...}, "timestamp": <unix ts>, "git_commit": "<short sha>"}`
- `GET /health` — `{"status": "ok", "git_commit": "<short sha>"}`

Every response includes `git_commit` — the short git SHA of the code that's
actually running, stamped in at deploy time (see below). Compare it against
`git rev-parse --short HEAD` locally to confirm the daemon isn't stale before
chasing a "bug" that's really just an un-deployed fix. A `-dirty` suffix means
the deployed file didn't match the last commit when it was pushed out.

## Deploy (systemd, Debian/Proxmox host)

Start from within this directory: `cd ./nvtop-daemon`

**Windows (PowerShell)** — uses the OpenSSH client built into Windows 11 for `ssh`/`scp`:
```powershell
$GitHash = git rev-parse --short HEAD
git diff --quiet -- vobot_gpu_daemon.py
if ($LASTEXITCODE -ne 0) { $GitHash = "$GitHash-dirty" }
$Stamped = Join-Path $env:TEMP 'vobot_gpu_daemon.stamped.py'
(Get-Content vobot_gpu_daemon.py -Raw) -replace '(?m)^GIT_COMMIT = .*', "GIT_COMMIT = `"$GitHash`"" |
    Set-Content -Path $Stamped -NoNewline -Encoding utf8

ssh root@proxmox "mkdir -p /opt/vobot-gpu-daemon"
scp $Stamped root@proxmox:/opt/vobot-gpu-daemon/vobot_gpu_daemon.py
scp vobot-gpu-daemon.service root@proxmox:/etc/systemd/system/
ssh root@proxmox "systemctl daemon-reload && systemctl restart vobot-gpu-daemon"
curl http://proxmox.home.lan:8039/api/gpu-data
```

**Linux/macOS (bash)**:
```bash
GIT_HASH=$(git rev-parse --short HEAD)$(git diff --quiet -- vobot_gpu_daemon.py || echo -dirty)
sed "s/^GIT_COMMIT = .*/GIT_COMMIT = \"$GIT_HASH\"/" vobot_gpu_daemon.py > /tmp/vobot_gpu_daemon.stamped.py

ssh root@proxmox "mkdir -p /opt/vobot-gpu-daemon"
scp /tmp/vobot_gpu_daemon.stamped.py root@proxmox:/opt/vobot-gpu-daemon/vobot_gpu_daemon.py
scp vobot-gpu-daemon.service root@proxmox:/etc/systemd/system/
ssh root@proxmox "systemctl daemon-reload && systemctl restart vobot-gpu-daemon"
curl http://proxmox.home.lan:8039/api/gpu-data
```

Runs as `nobody` — `/dev/nvidia*` on this host is world read/write so no
elevated privileges are needed to query the GPU.

## Config

No config file — the only tunable is `PORT` (default `8039`) at the top of
`vobot_gpu_daemon.py`. Multi-GPU hosts are handled automatically (`gpus` dict
gets one entry per GPU index); nothing to change.
