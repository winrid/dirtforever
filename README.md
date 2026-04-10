# DiRT Rally 2.0 Community Server

A community replacement for the defunct RaceNet/EgoNet backend that DiRT Rally 2.0 requires to play. Run it locally and the game's online features work without Codemasters servers.

---

## For Users

### Prerequisites

- Python 3.9+
- Windows (the hosts redirect requires editing `%WINDIR%\System32\drivers\etc\hosts`)
- DiRT Rally 2.0 installed via Steam
- `cryptography` Python package: `pip install cryptography`

### Quick Start

Run these steps once per machine, then start the server each session.

**1. Generate a TLS certificate**

```
python scripts/generate_dev_cert.py
```

Writes `runtime/certs/dr2server-cert.pem` and `runtime/certs/dr2server-key.pem`.

**2. Install the certificate into the Windows trust store**

```
powershell -ExecutionPolicy Bypass -File scripts/install_dev_cert.ps1
```

UAC will prompt for administrator access. This is required so the game accepts the self-signed cert.

**3. Redirect game traffic to localhost**

```
powershell -ExecutionPolicy Bypass -File scripts/setup_windows_redirect.ps1
```

Adds hosts entries for `prod.egonet.codemasters.com` and related Codemasters domains. UAC required.

**4. Start the server**

```
python server.py --ssl-cert runtime/certs/dr2server-cert.pem --ssl-key runtime/certs/dr2server-key.pem
```

The server listens on `127.0.0.1:8080` (HTTP) and `127.0.0.1:443` (HTTPS).

**5. Launch the game via Steam**

Start DiRT Rally 2.0 normally. Game traffic will reach the local server automatically.

### What Works

- Login
- Events (career mode loads without crashing)
- Clubs (server-defined custom events)

### What Does Not Work Yet

- Actual race result tracking
- Leaderboards
- Multiplayer

### Undoing the Hosts Redirect

```
powershell -ExecutionPolicy Bypass -File scripts/remove_windows_redirect.ps1
```

This removes the DR2 community server block from your hosts file. The certificate installed in step 2 can be removed manually via `certmgr.msc`.

---

## For Developers

### Project Layout

```
server.py                   entry point, delegates to dr2server/httpd.py main()
dr2server/
  httpd.py                  HTTP/HTTPS server, request capture, EgoNet RPC dispatch, upstream proxy
  dispatcher.py             RPC method handlers and fake response payloads
  egonet.py                 binary stream codec (encode/decode for EgoNet wire format)
  models.py                 typed data structures used by dispatcher and codec
  game_data.py              ID enums for locations, tracks, and vehicles
  account_store.py          file-per-account JSON storage
scripts/
  generate_dev_cert.py      generates self-signed cert covering all Codemasters hostnames
  install_dev_cert.ps1      installs cert into Windows current-user trust store
  setup_windows_redirect.ps1  adds hosts entries pointing Codemasters domains to 127.0.0.1
  remove_windows_redirect.ps1 removes those hosts entries
captures/                   raw JSON captures of every request and response
runtime/certs/              generated TLS cert and key
data/accounts/              one JSON file per account
```

### Architecture

The game makes HTTPS requests to `prod.egonet.codemasters.com` (and a few other Codemasters hostnames). The setup does two things:

1. The Windows hosts file redirects those hostnames to `127.0.0.1`.
2. A self-signed certificate covering those hostnames is installed as trusted, so the game's TLS verification passes.

Game traffic then arrives at the local Python HTTPS server on port 443. `httpd.py` decodes the EgoNet binary body, dispatches to a handler in `dispatcher.py`, and returns an EgoNet-encoded response.

### EgoNet Protocol

The game's RPC transport uses a custom binary stream format. Each value is length-prefixed and tagged with a type. The codec is in `egonet.py`.

The most important constraint: **types must match exactly**. The game distinguishes `si32`, `ui32`, and `ui08`. Sending the wrong integer type for a field causes an immediate crash, not a graceful error. Use the type aliases in `models.py` to ensure correct encoding.

### Required HTTP Headers

Every EgoNet RPC response must use:

- `Content-Type: text/html` (not `application/octet-stream`, the game validates this)
- `X-EgoNet-Catalogue-Version: 1.18.0`

### Adding a New RPC Handler

1. Add a function to `dispatcher.py` and register it in the handler map.
2. Return a dict using field names and types from `models.py`.
3. The codec in `egonet.py` handles encoding automatically based on the model types.

Field names must match exactly what the game expects. Unknown or missing fields cause crashes rather than fallback behavior.

### Upstream Proxy Mode

To forward selected EgoNet methods to the real Codemasters servers and capture their responses (useful for reverse engineering unknown payload shapes):

```
python server.py \
  --ssl-cert runtime/certs/dr2server-cert.pem \
  --ssl-key runtime/certs/dr2server-key.pem \
  --upstream-ip 159.153.126.42 \
  --proxy-all
```

`--proxy-all` forwards every method upstream. To proxy specific methods only:

```
  --upstream-ip 159.153.126.42 \
  --proxy-method RaceNetCareerLadder.GetRallyTierList \
  --proxy-method RaceNetCareerLadder.GetRallyChampionship
```

Captures of both the forwarded request and the upstream response are written to `captures/` in the usual JSON format.
