# DirtForever — DiRT Rally 2.0 Community Server

A community alternative to the RaceNet/EgoNet backend. Run a small local server that intercepts the game's network calls and connects to [dirtforever.net](https://dirtforever.net) for clubs, leaderboards, and stage results.

---

## Quick Start

### Setup (Windows)

1. Create an account at [dirtforever.net](https://dirtforever.net/register)
2. Log in, go to Dashboard, click **Generate Game Token**
3. Download [DirtForever.exe](https://github.com/winrid/dirtforever/releases/latest)
4. Run DirtForever.exe — it will set up everything and ask for your token
5. Launch DiRT Rally 2.0 via Steam

To play in future sessions, just run DirtForever.exe before launching the game.

### Setup (Linux, via Steam Proton)

1. Create an account at [dirtforever.net](https://dirtforever.net/register) and generate a Game Token from your Dashboard.
2. Download [DirtForever-linux-x86_64](https://github.com/winrid/dirtforever/releases/latest), `chmod +x` it, and run it.
3. Launch DR2 via Steam (Proton) at least once so the prefix exists, then click **START** in DirtForever. A polkit prompt asks for your password once to grant the binary port-443 access and add the redirect entries to `/etc/hosts`. The TLS cert is then installed into DR2's Proton prefix automatically (uses `protontricks-launch` if available, otherwise the bundled Proton wine).
4. Launch DiRT Rally 2.0 via Steam.

Or run from source: `git clone https://github.com/winrid/dirtforever && cd dirtforever && uv run python dirtforever.py`.

### What Works

- Login
- Clubs with custom server-defined events
- Stage time submission and leaderboards (via dirtforever.net)
- Vehicle select, repairs, tuning

### What Doesn't Work Yet

- Daily/Weekly/Monthly Events (although they do in Clubs). We could add this though, if people really want!
- Full championship progression
- Multiplayer / Time Trial ghosts
- In-game currency / store (uses placeholder data)

### Uninstalling

**Windows:**

```powershell
powershell -ExecutionPolicy Bypass -File scripts\remove_windows_redirect.ps1
```

Remove the certificate manually via `certmgr.msc` if desired. Config is stored at `%APPDATA%\DirtForever\config.json`.

**Linux:**

```sh
sudo sed -i '/# BEGIN DIRTFOREVER/,/# END DIRTFOREVER/d' /etc/hosts
protontricks-launch --appid 690790 certutil -delstore Root prod.egonet.codemasters.com
rm -rf ~/.config/dirtforever
```

---

## For Developers

### Layout

| Path | Purpose |
|---|---|
| `server.py` | Entry point |
| `dr2server/httpd.py` | HTTPS server, request capture, EgoNet RPC dispatch, upstream proxy |
| `dr2server/dispatcher.py` | RPC method handlers |
| `dr2server/egonet.py` | Binary stream codec (EgoNet wire format) |
| `dr2server/models.py` | Typed data structures for correct binary encoding |
| `dr2server/game_data.py` | IntEnum IDs for locations, tracks, vehicles |
| `dr2server/api_client.py` | REST client for dirtforever.net API |
| `dr2server/account_store.py` | Local account storage (fallback) |
| `web/` | Flask web frontend (dirtforever.net) |
| `scripts/` | Setup scripts (cert, hosts, installer) |
| `data/upstream_templates/` | Captured upstream binary responses used as templates |

### Architecture

```
Game Client  --EgoNet/HTTPS-->  Local Server (dr2server)  --REST-->  dirtforever.net
                                     |
                               reads config from
                          %APPDATA%\DirtForever\config.json
```

The Windows hosts file redirects `prod.egonet.codemasters.com` to `127.0.0.1`. A trusted self-signed cert makes TLS pass. The local server decodes EgoNet binary, calls dirtforever.net for persistent data, and encodes responses back.

### EgoNet Protocol

Custom binary format in `egonet.py`. **Types must match exactly** — the game crashes (not errors) if `si32` is sent where `ui32` is expected. Use the wrapper types (`UInt32`, `UInt8`, `Int64`, `Timestamp`) from `egonet.py` and the model classes in `models.py`.

All responses require `Content-Type: text/html` and `X-EgoNet-Catalogue-Version: 1.18.0`.

### Auth

Game tokens (`df_` + 32 hex chars) are generated on the dirtforever.net dashboard. The local server sends them as `Authorization: Bearer df_xxx` headers. The web API validates tokens and maps them to user accounts.

### Upstream Proxy Mode

Forward EgoNet calls to the real Codemasters servers for reverse engineering:

```
python server.py --ssl-cert ... --ssl-key ... --upstream-ip 159.153.126.42 --proxy-all
```

Per-method: `--proxy-method RaceNetCareerLadder.GetRallyChampionship`

### Adding RPC Handlers

1. Add handler in `dispatcher.py`, register in the handler map
2. Use `models.py` types for correct encoding (`UInt32`, `Int64`, etc.)
3. Field names must match the game's expectations exactly
