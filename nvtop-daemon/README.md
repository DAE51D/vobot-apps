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

- `GET /api/gpu-data` — `{"gpus": {"0": {...}}, "timestamp": <unix ts>}`
- `GET /health` — `{"status": "ok"}`

## Deploy (systemd, Debian/Proxmox host)

```bash
mkdir -p /opt/vobot-gpu-daemon
scp vobot_gpu_daemon.py root@proxmox:/opt/vobot-gpu-daemon/
scp vobot-gpu-daemon.service root@proxmox:/etc/systemd/system/
ssh root@proxmox "systemctl daemon-reload && systemctl enable --now vobot-gpu-daemon"
curl http://proxmox.home.lan:8039/api/gpu-data
```

Runs as `nobody` — `/dev/nvidia*` on this host is world read/write so no
elevated privileges are needed to query the GPU.

## Config

No config file — the only tunable is `PORT` (default `8039`) at the top of
`vobot_gpu_daemon.py`. Multi-GPU hosts are handled automatically (`gpus` dict
gets one entry per GPU index); nothing to change.
