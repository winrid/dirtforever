# Protocol Notes

These notes come from local static inspection of `F:\Steam\steamapps\common\DiRT Rally 2.0\dirtrally2.exe`.

## Known Hostnames

- `prod.egonet.codemasters.com`
- `qa.egonet.codemasters.com`
- `terms.codemasters.com`
- `aurora.codemasters.local`

## Known Method Names

- `Login.GetCurrentVersion`
- `Login.Login`
- `RaceNet.SignIn`
- `RaceNet.CreateAccount`
- `RaceNet.GetTermsAndConditions`
- `RaceNet.AcceptTerms`
- `RaceNet.CheckAccountLinked`
- `RaceNet.UnlinkAccount`
- `RaceNetLeaderboard.GetLeaderboardEntries`
- `RaceNetLeaderboard.GetFriendsEntries`
- `TimeTrial.GetLeaderboardId`
- `TimeTrial.PostTime`
- `Clubs.GetClubs`
- `Clubs.GetChampionshipLeaderboard`
- `Clubs.GetChampionshipFriendsLeaderboard`
- `Announcements.GetAnnouncements`
- `Localisation.GetStrings`
- `Status.GetNextStatusEvent`
- `Wallet.Get`
- `Inventory.Get`
- `Inventory.Purchase`
- `StoreSchema.Get`

## Immediate Hypothesis

The client likely uses an RPC-ish transport where:

- the hostname points at an EGONET service
- the request identifies a method name
- payload data is structured separately from the method name

The exact wire format is still unknown.

## Main Risks

1. The transport may be HTTPS only.
2. The payload may be protobuf or another binary envelope.
3. Some login paths may require Steam auth tickets in addition to username and password.
4. Successful startup may depend on more than one hostname.

## Recommended Capture Order

1. intercept first launch/login request
2. identify content type and framing
3. map required sequence of methods for menu entry
4. stub only the minimum responses required to progress further

## Club Championships — Multi-Event Model (verified 2026-07-07)

Ground-truthed by building a 2-event club championship on real RaceNet and
proxy-capturing `Clubs.GetClubs` + the drive lifecycle against upstream
(159.153.126.42). See `reference-verify-racenet-values` in memory for the
capture method and `tests/fixtures/captures/multi-event-r3/` for the captures.

**A multi-event championship is N separate Challenges, served one at a time —
NOT one Challenge holding N events.**

- The **`Club`** object is the only place the championship position lives:
  `AmountOfEvents = N` (total events) and `EventIndex` = current event (0-based).
  The UI's "Event 1 of 2" is `EventIndex=0 / AmountOfEvents=2`. Established clubs
  match: *Global Rallyfans* `Amount=3 EventIndex=2`, *Ray Charles Race*
  `Amount=12 EventIndex=10`.
- `Clubs.GetClubs` returns **only the currently-active event's Challenge**, with
  a **distinct `ChallengeID` and `EventId` per event**, each carrying its own
  `EntryWindow`. Windows are scheduled **back-to-back** (event k+1's `Start` ==
  event k's `End`), so a short event-1 window expires before you can enter it.
- Progression is **completion-driven and server-side**: finishing the active
  event advances the club's `EventIndex` (0→1) and the next `Clubs.GetClubs`
  serves the next event's Challenge. `EventIndex` caps at `N-1`; completing the
  last event fires `ChampionshipEnded` (keyed to that event's `challenge_id`).
  Observed transition: event 1 ChallengeID `946876`/EventId `948431` →
  event 2 ChallengeID `946877`/EventId `948432`, club `EventIndex` 0→1.
- **The game client never reports a championship-relative position.** Every
  event's `RaceNetChallenges.StageBegin` / `StageComplete` and the
  `DataMining.DataEvent` StageEnded telemetry report `EventIndex=0`,
  `event_count=1`, `StageIndex=0`, `stage_count=1` — from the client's view each
  served event is a standalone single-event championship. The championship
  position is encoded ONLY by which `ChallengeID` is active.

### Implication for this server

The earlier "flat-ordinal, multiple `Event`s inside one `Challenge`, non-zero
per-event `event_index`" assumption is **falsified**. Multi-event support must:

1. Emit `Club.AmountOfEvents = N` and `Club.EventIndex = current`.
2. Serve only the current event as its own single-event `Challenge` (own
   `ChallengeID`/`EventId`, own `EntryWindow`).
3. Advance `EventIndex` when that event's `StageComplete`/result arrives; serve
   the next event on the following `Clubs.GetClubs`.
4. NOT rely on game-supplied `event_index` (always 0) to sequence events.
