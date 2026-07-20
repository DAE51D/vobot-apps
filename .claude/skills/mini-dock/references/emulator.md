# Emulator

Use this reference when running or debugging apps in the Mini Dock simulator.

Source:
- MiniDock Emulator: https://dock.myvobot.com/developer/mini_dock_emulator/

## What The Emulator Provides

The simulator runs in Docker, opens an LVGL simulator window through X11, and mounts a local `disk` directory so apps can be edited and reloaded.

Useful locations:
- apps: `./disk/apps/...`
- config files: `./disk/conf/*.json`
- web configuration page: `http://localhost` when port 80 is mapped

Keyboard mapping:
- Enter: confirm
- Escape: cancel
- Left Arrow: encoder rotate counterclockwise
- Right Arrow: encoder rotate clockwise

## macOS

1. Install XQuartz.
2. In XQuartz settings, enable network client connections and disable connection authentication as needed.
3. Restart XQuartz.
4. Run `xhost +` from Terminal.
5. Start the simulator:

```bash
mkdir -p ~/work/minidock
cd ~/work/minidock
docker run \
  --rm -it \
  -v ./disk:/work/disk \
  -p 80:80 \
  vobot/mini-dock-app-dev:latest
```

If port 80 is occupied, map another host port, such as `-p 8080:80`.

## Linux

Install and start X11 if needed:

```bash
sudo apt install -y xorg xinit
startx
```

Allow X11 forwarding from clients:

```bash
xhost +
```

Run with host networking:

```bash
mkdir -p ~/work/minidock
cd ~/work/minidock
docker run \
  --rm -it \
  -v ./disk:/work/disk \
  --network=host \
  vobot/mini-dock-app-dev:latest
```

If host networking or port 80 is not suitable, use port mapping:

```bash
docker run \
  --rm -it \
  -v ./disk:/work/disk \
  -p 8080:80 \
  --add-host host.docker.internal:host-gateway \
  vobot/mini-dock-app-dev:latest
```

## Windows WSL2

Official setup outline:
1. Use Windows 10 version 1903 or later, or Windows 11.
2. Enable WSL and Virtual Machine Platform.
3. Install the Linux kernel update package.
4. Set WSL 2 as default.
5. Install a Linux distribution, such as Ubuntu.
6. Initialize the distribution.
7. Check with `wsl -l -v`.
8. Install an X server such as VcXsrv.
9. Install Docker in WSL2.

Run from WSL2:

```bash
export DISPLAY="192.168.1.1:0"
mkdir -p /mnt/d/work/minidock
cd /mnt/d/work/minidock
docker run \
  --rm -it \
  -v $(pwd)/disk:/work/disk \
  --network=host \
  -e DISPLAY=$DISPLAY \
  vobot/mini-dock-app-dev:latest
```

Edit apps under `D:/work/minidock/disk/apps/...` and rerun the Docker command to reload.

