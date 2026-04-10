# DiRT Rally 2.0 Community Server Handoff

## Purpose

This repo is a local bootstrap/emulation server for `DiRT Rally 2.0` intended to replace the RaceNet / EgoNet backend with a community-controlled service.

The immediate goal is not full feature parity. The current milestone is:

- keep login working
- make `Events` load without crashing
- make `Clubs` load with fake data
- keep capturing enough real request/response shape to continue replacing stubs with concrete implementations

This working directory is **not** a git checkout.

## Repo Layout

- [server.py](/C:/Users/winrid/dr2server/server.py)
- [README.md](/C:/Users/winrid/dr2server/README.md)
- [dr2server/httpd.py](/C:/Users/winrid/dr2server/dr2server/httpd.py)
- [dr2server/dispatcher.py](/C:/Users/winrid/dr2server/dr2server/dispatcher.py)
- [dr2server/egonet.py](/C:/Users/winrid/dr2server/dr2server/egonet.py)
- [dr2server/account_store.py](/C:/Users/winrid/dr2server/dr2server/account_store.py)
- [scripts/dr2_control.ahk](/C:/Users/winrid/dr2server/scripts/dr2_control.ahk)
- [scripts/run_game_flow.ps1](/C:/Users/winrid/dr2server/scripts/run_game_flow.ps1)
- [notes/how_to_control_game.md](/C:/Users/winrid/dr2server/notes/how_to_control_game.md)
- [captures](/C:/Users/winrid/dr2server/captures)
- [runtime/gamebot](/C:/Users/winrid/dr2server/runtime/gamebot)
- [data/accounts](/C:/Users/winrid/dr2server/data/accounts)

## What Works Right Now

- local HTTP and HTTPS backend is implemented in Python
- hosts redirection for Codemasters endpoints is already in place on this machine
- local certificate trust is already installed on this machine
- game traffic reaches the local server
- login works in-game
- EgoNet request bodies are captured and decoded
- EgoNet response bodies are also captured
- file-per-account storage works
- basic web UI exists for account creation and login testing
- game automation is partially working through AutoHotInterception

## What Does Not Work Yet

- `Events` still crashes the game
- `Clubs` does not yet load successfully in the game
- several backend payloads are still inferred rather than validated against real upstream responses
- automation timing is still fragile on cold starts

## Current Hypothesis

The transport problem is solved. The remaining failures are protocol-shape problems.

The `Events` crash is strongly associated with the rally ladder / championship branch:

- `RaceNetCareerLadder.GetRallyTierList`
- `RaceNetCareerLadder.GetRallyChampionship`
- `RaceNetCareerLadder.ResetRallyChampionship`

Returning failure codes for those methods did **not** prevent the crash. The client appears to require a valid success payload, not just a graceful error.

## Current Server Behavior

### Entry Points

- HTTP: `127.0.0.1:8080`
- HTTPS: `127.0.0.1:443`

### Important Files

- [dr2server/httpd.py](/C:/Users/winrid/dr2server/dr2server/httpd.py)
  - request capture
  - response capture
  - HTTP form/json endpoints
  - EgoNet RPC handling
- [dr2server/dispatcher.py](/C:/Users/winrid/dr2server/dr2server/dispatcher.py)
  - handler map for all emulated methods
  - most of the fake data payloads
- [dr2server/egonet.py](/C:/Users/winrid/dr2server/dr2server/egonet.py)
  - EgoNet binary stream encode/decode
  - nested `vdic` / `vvtr` decoding support already added

### Important Methods Currently Stubbed or Partially Implemented

Implemented enough to get login working:

- `Login.GetCurrentVersion`
- `Login.Login`
- `Login.Tick`
- `RaceNet.SignIn`
- `RaceNet.CreateAccount`
- `RaceNet.GetTermsAndConditions`
- `RaceNet.AcceptTerms`
- `DataMining.DataEvent`
- `RaceNetInventory.GetInventory`
- `RaceNetInventory.GetStore`
- `RaceNetInventory.GetRewards`
- `Announcements.GetAnnouncements`
- `Status.GetNextStatusEvent`
- `Advertising.EnabledCheck`
- `VanityFlags.GetVanityFlags`
- `Staff.GetStaff`
- `Season.Get`
- `Esports.SeasonActivityCheck`
- `Esports.EnabledCheck`
- `Esports.ActivityCheck`
- `Esports.HasAcceptedTerms`

Likely problem area:

- `RaceNetCareerLadder.GetRallyTierList`
- `RaceNetCareerLadder.GetRallycrossTierList`
- `RaceNetCareerLadder.GetRallyChampionship`
- `RaceNetCareerLadder.GetRallycrossChampionship`
- `RaceNetCareerLadder.ResetRallyChampionship`
- `RaceNetCareerLadder.ResetRallycrossChampionship`

`Clubs` is not yet complete:

- `Clubs.GetClubs` exists and returns a fake club list
- no deeper `Clubs.*` flow has been implemented yet beyond what was needed for initial probing

## Current Fake Payloads

### Clubs

`Clubs.GetClubs` currently returns one club:

- `ClubId: 1`
- `Name: "Community Test Club"`
- `CreatorName: "HappyHydra"`
- `HasStandings: true`
- `IsOtherPlatform: false`
- `AmountOfEvents: 1`
- `IsUpcoming: false`
- `ClubLimit: 32`
- `InclCrossPlat: true`

### Rally Ladder

`GetRallyTierList` currently returns:

- `TierList` with a few entries containing:
  - `DriverID`
  - `StageTime`
  - `Points`
- `PrevPlayerTier`
- `PlayerTier`
- `ChallengeType`
- `ScoringType`

`GetRallyChampionship` and `ResetRallyChampionship` currently return a large fake structure with fields like:

- `ChallengeId`
- `Name`
- `EventIndex`
- `StageIndex`
- `State`
- `StageTimeMs`
- `VehicleInstId`
- `MetersDriven`
- `Percentile`
- `ChampTimeMs`
- `HasRepaired`
- `RepairPenalty`
- `VehicleDamage`
- `VehicleMud`
- `TyreCompound`
- `TyresRemaining`
- `TuningSetup`
- `AttemptsLeft`
- `Events`
- `Vehicle`

That payload is still guesswork and is the prime suspect.

## Known Good / Bad Runtime Behavior

### Good

- user can reach login
- local backend is definitely receiving real HTTPS requests from the game

### Bad

- selecting `Events` causes a crash after the ladder/championship requests
- selecting `Clubs` reports server unavailable

## How Crash Detection Should Be Done

Do **not** infer success from a screenshot taken mid-transition.

Use process state:

- success means `dirtrally2.exe` is still running and `CrashSender1405.exe` is **not** open
- crash means `CrashSender1405.exe` exists or `dirtrally2.exe` exited unexpectedly

This matters because the game can sit on a loading screen briefly before crashing.

## Latest Confirmed Crash Sequence

The last meaningful `Events` path before crash reached:

- `Login.GetCurrentVersion`
- `Login.Login`
- `RaceNetInventory.GetInventory`
- `DataMining.DataEvent`
- `VanityFlags.GetVanityFlags`
- `Staff.GetStaff`
- `RaceNetInventory.GetStore`
- `DataMining.DataEvent`
- `RaceNetInventory.GetRewards`
- `Announcements.GetAnnouncements`
- `RaceNetInventory.GetInventory`
- `Advertising.EnabledCheck`
- `Season.Get`
- `Status.GetNextStatusEvent`
- `RaceNetInventory.GetRewards`
- `Esports.SeasonActivityCheck`
- `RaceNetCareerLadder.GetRallyTierList`
- `RaceNetCareerLadder.GetRallyChampionship`
- `RaceNetCareerLadder.ResetRallyChampionship`

After that, the user observed the game crash and `CrashSender1405.exe` was present.

## Environment Setup On This Machine

### Game

- game path: `F:\Steam\steamapps\common\DiRT Rally 2.0\dirtrally2.exe`
- Steam app id: `690790`

### Installed Tools

- AutoHotkey v2
  - `C:\Program Files\AutoHotkey\v2\AutoHotkey64.exe`
- NirCmd
  - `C:\Users\winrid\Downloads\nircmd-x64\nircmd.exe`
- Tesseract OCR
  - `C:\Program Files\Tesseract-OCR\tesseract.exe`
- AutoHotInterception
  - `C:\Users\winrid\Downloads\AutoHotInterception\AHK v2`
- Interception driver

### Keyboard IDs Discovered For AutoHotInterception

The current automation sends key events across all of these:

- `1 keyboard VID=0x320F PID=0x5000 HANDLE=HID\VID_320F&PID_5000&REV_0100&MI_00`
- `2 keyboard VID=0x320F PID=0x5000 HANDLE=HID\VID_320F&PID_5000&REV_0100&MI_01&Col01`
- `3 keyboard VID=0x1532 PID=0x005C HANDLE=HID\VID_1532&PID_005C&REV_0200&MI_01&Col01`
- `4 keyboard VID=0x1532 PID=0x005C HANDLE=HID\VID_1532&PID_005C&REV_0200&MI_02`
- `5 keyboard VID=0x046D PID=0xC52B HANDLE=HID\VID_046D&PID_C52B&REV_1211&MI_00`
- `6 keyboard VID=0x046D PID=0xC232 HANDLE=HID\VID_046D&PID_C232`

## Automation State

### Files

- [scripts/dr2_control.ahk](/C:/Users/winrid/dr2server/scripts/dr2_control.ahk)
- [scripts/run_game_flow.ps1](/C:/Users/winrid/dr2server/scripts/run_game_flow.ps1)

### What It Does

- launches the game if not already running
- focuses the game window
- injects keyboard input using AutoHotInterception
- takes a screenshot with NirCmd
- OCRs the screenshot with Tesseract
- stores artifacts in [runtime/gamebot](/C:/Users/winrid/dr2server/runtime/gamebot)

### Important Detail

Plain AHK `Send` / `ControlSend` did **not** work for this game. AutoHotInterception is required.

### Current Actions

- `start`
- `events`
- `clubs`
- `freeplay`

### Current Timing

The current AHK script uses:

- `LaunchGame()` sleep: `30000`
- `DriveStartScreen()`:
  - press `Enter` 8 times
  - `3000 ms` between presses
- `DriveEvents()`:
  - one `Enter`
  - wait `8000 ms`

This was patched because earlier runs hit `Enter` too early on cold start and only captured the logo screen.

## How To Run Automation

Example:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_game_flow.ps1 -Action events
```

Artifacts are written under:

- [runtime/gamebot](/C:/Users/winrid/dr2server/runtime/gamebot)

Useful recent paths:

- [runtime/gamebot/20260409-221244](/C:/Users/winrid/dr2server/runtime/gamebot/20260409-221244)
- [runtime/gamebot/20260409-220859](/C:/Users/winrid/dr2server/runtime/gamebot/20260409-220859)
- [runtime/gamebot/20260409-220509](/C:/Users/winrid/dr2server/runtime/gamebot/20260409-220509)
- [runtime/gamebot/crash-state.png](/C:/Users/winrid/dr2server/runtime/gamebot/crash-state.png)
- [runtime/gamebot/post-crash-check.png](/C:/Users/winrid/dr2server/runtime/gamebot/post-crash-check.png)

## Request / Response Capture

### Capture Directory

- [captures](/C:/Users/winrid/dr2server/captures)

Recent files at time of handoff:

- [captures/20260409-221319-1775797999347558400.json](/C:/Users/winrid/dr2server/captures/20260409-221319-1775797999347558400.json)
- [captures/20260409-221319-1775797999282875600.json](/C:/Users/winrid/dr2server/captures/20260409-221319-1775797999282875600.json)
- [captures/20260409-221319-1775797999217572200.json](/C:/Users/winrid/dr2server/captures/20260409-221319-1775797999217572200.json)

### Capture Format

Each capture JSON includes:

- request method/path/query
- request headers
- raw request body
- base64 request body
- decoded EgoNet body
- response headers
- response body

Response capture was added specifically so payload debugging can be based on what was actually sent, not what the code was assumed to send.

## Host Redirect / TLS Notes

The Windows `hosts` file on this machine was already updated to redirect:

- `prod.egonet.codemasters.com`
- `qa.egonet.codemasters.com`
- `terms.codemasters.com`
- `aurora.codemasters.local`

The local cert trust setup was already completed on this machine.

This is why HTTPS requests now reach the Python server correctly.

## Steam / Crash Reporter Notes

### Steam

Steam itself was not broken by the Codemasters host overrides.

After a reboot, Steam got stuck with launcher processes and had to be cleaned up by killing:

- `steam.exe`
- `steamwebhelper.exe`

Then relaunching Steam fixed it.

### Crash Reporter

When the game crashes, it may leave `CrashSender1405.exe` running. That can block relaunches until it is closed.

Before each automated test run, check for and kill:

- `CrashSender1405.exe`
- stray `dirtrally2.exe` from previous failed runs if needed

## Most Important Binary Strings Already Observed

These strings were extracted from the game and heavily suggest the fields the client validates on the events path.

### Rally Ladder / Championship

- `eInvalidModeState`
- `eInvalidTierList`
- `eInvalidVehicleDesciption`
- `eInvalidChampionshipDescription`
- `eInvalidProgressIndex_GameAheadOfServer`
- `eInvalidProgressIndex_ServerAheadOfGame`
- `DriverID`
- `StageTime`
- `Points`
- `TierList`
- `PrevPlayerTier`
- `PlayerTier`
- `ChallengeType`
- `ScoringType`
- `ChallengeId`
- `EventIndex`
- `StageIndex`
- `State`
- `StageTimeMs`
- `VehicleInstId`
- `MetersDriven`
- `Percentile`
- `ChampTimeMs`
- `HasRepaired`
- `RepairPenalty`
- `VehicleDamage`
- `VehicleMud`
- `TyreCompound`
- `TyresRemaining`
- `TuningSetup`
- `AttemptsLeft`
- `Requirements`
- `Reward`
- `MinEventCredits`
- `MaxEventCredits`
- `EntryWindow`
- `NumEntrants`
- `DifficultyLevel`
- `IsHardcore`
- `ExteriorCams`
- `Category`
- `Mode`
- `DirtPlusSeason`
- `IsPromo`
- `Events`
- `ClubId`
- `EsportsMonthId`
- `AllowAssists`
- `UnxpectdMoments`
- `UseInvVehicle`
- `AttemptsAllowed`

### Vehicle Shape Hints

- `Id`
- `EntitlementId`
- `LiveryId`
- `UpgradeId`
- `Differential`
- `Wheels`
- `VehicleId`
- `TuningId`
- `UpgAvailable`
- `UpgEnabled`
- `TuningReady`
- `TuningPurchased`
- `IsNew`
- `IsRepairFree`
- `IsSellable`
- `Damage`
- `CompDamage`
- `SellPrice`
- `ResearchTarget`
- `ResearchPercent`
- `IsLocked`
- `LockEntity`
- `LockChallengeId`
- `LockReason`
- `LockExpiry`
- `LockLocation`
- `DistanceDriven`
- `Podiums`
- `EventsEntered`
- `EventsFinished`
- `Terminals`
- `ItemType`

### Clubs Shape Hints

- `CreatorName`
- `HasStandings`
- `IsOtherPlatform`
- `AmountOfEvents`
- `IsUpcoming`
- `Clubs.GetClubs`
- `ClubLimit`
- `InclCrossPlat`
- `Clubs`
- `eInvalidClubId`
- `eInvalidClubName`
- `eInvalidChallengeClubId`
- `eInvalidRequirements`
- `eInvalidScoringType`
- `eInvalidType`
- `eInvalidEndTime`
- `eInvalidNumberOfEvents`
- `eInvalidLocation`
- `eInvalidNumberOfStages`
- `eInvalidTrackModel`
- `eInvalidStageConditions`
- `eInvalidSurfaceDegradation`
- `eMissingTrackEntitlement`
- `eMissingVehicleClassEntitlement`

## Recommended Next Step

Do not keep blindly guessing ladder payloads.

The best next step is to add **optional upstream forwarding** for selected EgoNet methods so real Codemasters responses can be used as a reference while the official servers are still available.

### Why

- we already terminate TLS locally
- we already decode requests
- we already capture responses
- the remaining failures are almost certainly field-shape / required-value problems

### Suggested Implementation

Add proxy support in [dr2server/httpd.py](/C:/Users/winrid/dr2server/dr2server/httpd.py), inside or adjacent to `_handle_egonet_rpc`, controlled by config or CLI flags.

Example design:

- `--upstream-host prod.egonet.codemasters.com`
- `--proxy-method RaceNetCareerLadder.GetRallyTierList`
- `--proxy-method RaceNetCareerLadder.GetRallyChampionship`
- `--proxy-method RaceNetCareerLadder.ResetRallyChampionship`
- `--proxy-method Clubs.GetClubs`

Proxy behavior:

1. receive local game request
2. if method is proxied, forward the exact request upstream over HTTPS
3. capture:
   - upstream status
   - upstream headers
   - upstream raw body
   - decoded upstream EgoNet body
4. relay upstream response back to the game
5. use that captured response to shape the local fake implementation later

This is the highest-value next change.

## Practical Work Plan For The Next Developer

1. Verify server is running and login still works.
2. Add optional upstream proxying for selected EgoNet methods.
3. Proxy the three rally ladder methods first:
   - `RaceNetCareerLadder.GetRallyTierList`
   - `RaceNetCareerLadder.GetRallyChampionship`
   - `RaceNetCareerLadder.ResetRallyChampionship`
4. Run the `events` automation flow.
5. Confirm whether relaying real upstream responses stops the crash.
6. If yes, preserve captures and replace those responses with stable local fake data that matches the observed shape.
7. Then repeat for `Clubs`.
8. Keep using `CrashSender1405.exe` and `dirtrally2.exe` process state as the final success/failure signal.

## Warnings / Gotchas

- do not trust screenshots alone to determine success
- do not assume a structurally similar payload is sufficient; the client appears strict
- the game may crash after a short loading delay, so wait before concluding a run passed
- `CrashSender1405.exe` can block relaunches if not cleaned up
- cold-start timing is different from warm-start timing
- this repo is not in git, so there is no branch/commit safety net

## One-Sentence Summary

Transport interception, login, capture, and basic automation all work; the remaining blocker is accurately emulating the rally ladder and club backend payloads, and the fastest path forward is to proxy selected methods to the real server and use those responses as the reference shape.
