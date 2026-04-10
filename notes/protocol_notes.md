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
