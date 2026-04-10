# DirtForever — DiRT Rally 2.0 Community Server

A community replacement for the defunct RaceNet/EgoNet backend. Run a small local server that intercepts the game's network calls and connects to [dirtforever.net](https://dirtforever.net) for clubs, leaderboards, and stage results.

---

## Quick Start

### Prerequisites

- Windows 10/11
- Python 3.9+ ([python.org](https://www.python.org/downloads/))
- `cryptography` package: `pip install cryptography`
- DiRT Rally 2.0 installed via Steam

### Setup (one time)

1. Create an account at [dirtforever.net](https://dirtforever.net/register)
2. Log in and go to your [Dashboard](https://dirtforever.net/dashboard) — click **Generate Game Token** and copy it
3. Open **PowerShell as Administrator** and run:

```powershell
cd path\to\dr2server
powershell -ExecutionPolicy Bypass -File scripts\install.ps1
```

The installer will:
- Generate and trust a local TLS certificate
- Redirect Codemasters hostnames to your machine
- Ask you to paste your game token
- Create a **DirtForever Server** desktop shortcut

### Playing

1. Double-click the **DirtForever Server** shortcut (or run `python server.py --ssl-cert runtime\certs\dr2server-cert.pem --ssl-key runtime\certs\dr2server-key.pem`)
2. Launch DiRT Rally 2.0 via Steam
3. Play — clubs, events, and leaderboards are served by dirtforever.net

### What Works

- Login
- Events / Career mode
- Clubs with custom server-defined events
- Stage time submission and leaderboards (via dirtforever.net)
- Vehicle select, repairs, tuning

### What Doesn't Work Yet

- Full championship progression
- Multiplayer / Time Trial ghosts
- In-game currency / store (uses placeholder data)

### Uninstalling

```powershell
powershell -ExecutionPolicy Bypass -File scripts\remove_windows_redirect.ps1
```

Remove the certificate manually via `certmgr.msc` if desired. Config is stored at `%APPDATA%\DirtForever\config.json`.

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
