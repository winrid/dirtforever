# DiRT Rally 2.0 Community Server Bootstrap

This repository is a Python proof of concept for emulating parts of the DiRT Rally 2.0 backend.

The first goal is not a full replacement. The first goal is to:

- capture requests the game makes
- stub known RaceNet style methods
- provide a basic website/API for account creation
- store each account in its own JSON file

## What We Already Know

Static string inspection of `dirtrally2.exe` shows these likely backend hostnames:

- `prod.egonet.codemasters.com`
- `qa.egonet.codemasters.com`
- `terms.codemasters.com`
- `aurora.codemasters.local`

It also exposes backend-style method names including:

- `Login.Login`
- `Login.GetCurrentVersion`
- `RaceNet.SignIn`
- `RaceNet.CreateAccount`
- `RaceNet.GetTermsAndConditions`
- `RaceNet.AcceptTerms`
- `Clubs.GetClubs`
- `RaceNetLeaderboard.GetLeaderboardEntries`
- `TimeTrial.PostTime`

That strongly suggests the game talks to an HTTP or HTTPS API with RPC-like operation names on top.

## Important Constraint

Steam is probably not the hardest part.

The harder part is that the game likely talks to Codemasters services over HTTPS. Pointing DNS or the hosts file at your own server is easy. Making the client accept your TLS certificate requires one of these:

1. a trusted local certificate for the original hostname
2. a TLS interception setup such as `mitmproxy`
3. a binary patch that disables certificate checks or rewrites backend URLs

Launching outside Steam may help with iteration, but it will not by itself replace the RaceNet backend.

## Quick Start

```powershell
python .\scripts\generate_dev_cert.py
powershell -ExecutionPolicy Bypass -File .\scripts\install_dev_cert.ps1
python server.py --host 127.0.0.1 --port 8080 --https-port 443 --ssl-cert .\runtime\certs\dr2server-cert.pem --ssl-key .\runtime\certs\dr2server-key.pem
```

Open:

- `http://127.0.0.1:8080/` for a tiny web UI
- `http://127.0.0.1:8080/api/health` for health

## Layout

- `server.py`: entry point
- `dr2server/account_store.py`: file-per-account storage
- `dr2server/dispatcher.py`: method dispatch and stub responses
- `dr2server/httpd.py`: HTTP server and request capture
- `scripts/setup_windows_redirect.ps1`: adds Windows hosts redirects with UAC elevation
- `scripts/remove_windows_redirect.ps1`: removes those hosts redirects
- `scripts/generate_dev_cert.py`: generates a local TLS certificate and key
- `scripts/install_dev_cert.ps1`: trusts that certificate for the current Windows user
- `captures/`: raw captured requests from the game or browser
- `data/accounts/`: one JSON file per account

## Current Endpoints

- `GET /`
- `GET /register`
- `GET /login`
- `POST /api/account/register`
- `POST /api/account/login`
- `GET /api/health`
- `POST /rpc`
- `POST /rpc/<method>`

`POST /rpc` accepts JSON such as:

```json
{
  "method": "Login.Login",
  "params": {
    "username": "driver1",
    "password": "secret"
  }
}
```

## Suggested Reverse Engineering Workflow

1. Redirect `prod.egonet.codemasters.com` to your machine with a hosts override or local DNS.
2. Terminate TLS for that hostname with a cert the machine trusts.
3. Run this Python server or place it behind a reverse proxy.
4. Launch the game and inspect files written to `captures/`.
5. Add handlers for whatever the client expects next.

## Windows Redirect Helper

For local testing on Windows:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup_windows_redirect.ps1 -ServerIp 127.0.0.1
```

This script:

- prompts for UAC elevation if needed
- adds hosts entries for the known Codemasters backend names
- is safe to run repeatedly because it rewrites only its own marked block

To remove the redirect:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\remove_windows_redirect.ps1
```

## Certificate Helper

Generate and trust a local certificate for the current user:

```powershell
python .\scripts\generate_dev_cert.py
powershell -ExecutionPolicy Bypass -File .\scripts\install_dev_cert.ps1
```

Then start the server with HTTPS enabled on `443`:

```powershell
python server.py --host 127.0.0.1 --port 8080 --https-port 443 --ssl-cert .\runtime\certs\dr2server-cert.pem --ssl-key .\runtime\certs\dr2server-key.pem
```

## Local UI Automation

For repeatable local menu navigation on Windows:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_game_flow.ps1 -Action events
powershell -ExecutionPolicy Bypass -File .\scripts\run_game_flow.ps1 -Action clubs
```

This wrapper:

- launches or focuses `DiRT Rally 2.0`
- sends the fixed key sequence from `notes/how_to_control_game.md`
- captures a full-screen screenshot with `nircmd`
- runs OCR with `tesseract`
- writes artifacts under `runtime/gamebot/<timestamp>`

## What You Can And Cannot Automate

You can automate admin-required local changes such as:

- hosts file updates
- local firewall rules
- installing your own trusted certificate for your own redirector

You should not rely on "silent" admin access. On normal Windows machines, the correct pattern is to relaunch the setup step with `RunAs` so the user sees the UAC prompt.

For other users, the clean distribution model is:

1. ship the community server
2. ship a setup script or installer that requests admin once
3. add hosts entries or local DNS settings
4. install a trusted certificate if HTTPS interception is needed

The script in this repo now covers step 2 and the hosts-file part of step 3.

## Next Steps

- confirm exact request shape the game uses
- identify whether payloads are JSON, protobuf, or another framed format
- determine whether Steam auth tickets are required for login
- expand handlers for profile, clubs, leaderboards, and time trial flows
