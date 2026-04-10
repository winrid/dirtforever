# Club Events — Developer Spec

## Overview

Club owners can create events (rally challenges) through the web UI. The game server fetches these via `GET /api/game/clubs` and converts them to in-game club challenges.

## Event Data Structure

Events are stored as JSON in `web/data/events/{event_id}.json`. The game server reads these fields:

```json
{
  "id": "evt-abc123",
  "name": "Weekend Wales Rally",
  "type": "weekly",
  "location": "Wales",
  "car_class": "Group A",
  "surface": "Gravel",
  "conditions": "Clear",
  "stages": [
    {"name": "Sweet Lamb", "distance_km": 9.9, "conditions": "Clear"},
    {"name": "Pant Mawr", "distance_km": 5.0, "conditions": "Clear"}
  ],
  "start_time": "2026-04-10T12:00:00",
  "end_time": "2026-04-17T12:00:00",
  "active": true,
  "featured": false,
  "club_id": "club-628bb8f9"
}
```

### Required fields

| Field | Type | Description |
|---|---|---|
| `id` | string | Unique ID (generate with `f"evt-{uuid4().hex[:8]}"`) |
| `name` | string | Display name shown in-game |
| `type` | string | `"daily"`, `"weekly"`, or `"monthly"` |
| `location` | string | Must match a location name below |
| `car_class` | string | Must match a vehicle class name below |
| `stages` | array | 1-8 stages, each with `name`, `distance_km`, `conditions` |
| `start_time` | ISO datetime | When the event opens |
| `end_time` | ISO datetime | When the event closes |
| `active` | bool | Set true while event is running |
| `club_id` | string | The club this event belongs to |

### How the game server uses this

The game server calls `GET /api/game/clubs` which returns all clubs + their active events. It then:

1. Maps `location` string to a game LocationId
2. Picks track routes from that location (one per stage)
3. Maps `car_class` to a vehicle class requirement
4. Builds the in-game challenge structure

The **stage names don't matter** for the game — the game server picks actual track routes based on the location. The number of stages in the `stages` array determines how many routes are assigned.

## Available Locations

Use these exact strings for the `location` field:

| Location | LocationId | Stages available | Surface |
|---|---|---|---|
| Sweden | 2 | 4 | Snow/Ice |
| Wales | 3 | 7 | Gravel |
| Argentina | 5 | 4 | Gravel |
| New England | 10 | 1 | Gravel |
| Poland | 13 | 4 | Tarmac/Gravel |
| Germany | 14 | 4 | Tarmac |
| New Zealand | 16 | 12 | Gravel/Tarmac |
| France | 17 | 12 | Tarmac |
| Yas Marina | 19 | 1 | Rallycross |
| Montalegre | 20 | 1 | Rallycross |
| Australia | 31 | 11 | Gravel |
| Scotland | 34 | 12 | Gravel |
| Spain | 36 | 12 | Tarmac |
| Finland | 37 | 12 | Gravel |
| Greece | 46 | 4 | Tarmac |

Locations with no confirmed track IDs (won't appear in-game): Monte Carlo.

## Available Vehicle Classes

Use these exact strings for the `car_class` field:

| Class | Era/Type |
|---|---|
| H1 FWD | Historic 1960s FWD |
| H2 FWD | Historic 1970s FWD |
| H2 RWD | Historic 1970s RWD |
| H3 RWD | Historic 1980s RWD |
| Group B RWD | Group B RWD |
| Group B 4WD | Group B 4WD |
| Group A | Group A (1990s) |
| R2 | Modern R2 |
| F2 Kit Car | F2 Kit Car |
| R5 | Modern R5 |
| Rally GT | Rally GT |
| NR4/R4 | NR4/R4 |
| 2000cc 4WD | 2000cc 4WD |
| RX Super 1600 | Rallycross Super 1600 |
| RX Supercars | Rallycross Supercars |
| RX Supercars 2019 | Rallycross Supercars 2019 |

## UI Requirements

### Create Event form (on club detail page)

Fields:
- **Event name** (text input)
- **Location** (dropdown — the location list above)
- **Vehicle class** (dropdown — the class list above)
- **Number of stages** (1-8, limited by location's available tracks)
- **Duration** (preset: 24h / 1 week / 1 month, or custom start/end)

On submit:
1. Generate event ID
2. Build `stages` array (use the stage names from the location, or just `{"name": "Stage N", "distance_km": 7.0, "conditions": "Clear"}`)
3. Save with `save_event()`
4. Set `active: true`, `club_id` to the current club's ID

### Existing helpers

- `save_event(event_dict)` — saves to `web/data/events/{id}.json`
- `get_event(event_id)` — loads event
- `get_all_events()` — lists all events
- `get_events_by_type(type)` — filter by daily/weekly/monthly

### API flow

```
Web UI → save_event() → JSON file
                              ↓
Game server → GET /api/game/clubs → reads clubs + events → serves to game
```

No real-time sync needed — the game server fetches fresh data on each Clubs.GetClubs call.
