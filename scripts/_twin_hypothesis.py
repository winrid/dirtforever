"""Test whether each twin id selects a distinct lighting file.

Poland ships sunset_overcast but not sunset_dry, and id 42 loaded correctly
there while 16 broke -- so the twins are not duplicates: they pick different
lighting. If each twin maps to one lighting file, the location archives (which
list the lighting_<tod>_<weather>_00.xml files each location ships) decide
which twin a location can load, with no further in-game tests.
"""
import collections
import glob
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from dr2server.egonet import decode_stream          # noqa: E402
from dr2server.game_data import TRACKS, Location    # noqa: E402

GAMEDIR = Path("F:/Steam/steamapps/common/DiRT Rally 2.0/locations")
ARCH = {
    'australia__australia_rally': 'AUSTRALIA', 'south_america__argentina_rally': 'ARGENTINA',
    'spain__spain_rally': 'SPAIN', 'poland__poland_rally': 'POLAND',
    'new_zealand__new_zealand_rally': 'NEW_ZEALAND', 'usa__usa_rally': 'NEW_ENGLAND',
    'usa__twin_peaks': 'TWIN_PEAKS', 'germany__germany_rally': 'GERMANY',
    'greece__greece_rally': 'GREECE', 'finland__finland_rally': 'FINLAND',
    'sweden__sweden_rally': 'SWEDEN', 'uk__wales_rally': 'WALES',
    'uk__scotland_rally': 'SCOTLAND', 'france__france_rally': 'MONTE_CARLO',
    'belgium__mettet_rallycross': 'METTET', 'canada__trois_rivieres': 'TROIS_RIVIERES',
    'uk__lydden_hill_rallycross': 'LYDDEN_HILL', 'uk__silverstone_rallycross': 'SILVERSTONE',
    'france__loheac_rallycross': 'LOHEAC', 'germany__estering_rallycross': 'ESTERING',
    'latvia__riga_rallycross': 'BIKERNIEKI', 'norway__hell_rallycross': 'HELL',
    'portugal__montalegre_rallycross': 'MONTALEGRE',
    'south_africa__killarney_rallycross': 'KILLARNEY',
    'spain__barcelona_rallycross': 'BARCELONA', 'sweden__holjes_rallycross': 'HOLJES',
    'uae__yas_marina_rallycross': 'YAS_MARINA',
}


def lighting_by_location():
    out = collections.defaultdict(set)
    encrypted = set()
    for f in sorted(glob.glob(str(GAMEDIR / '*.nefs'))):
        base = os.path.basename(f)
        loc = next((v for k, v in ARCH.items() if base.startswith(k)), None)
        if not loc:
            continue
        with open(f, 'rb') as fh:
            data = fh.read(32 * 1024 * 1024)
        names = {m.decode()[9:-7] for m in re.findall(rb'lighting_[a-z0-9_]+\.xml', data)}
        if names:
            out[loc] |= names
        else:
            encrypted.add(loc)
    return out, encrypted - set(out)


def racenet_officials():
    """Ids RaceNet's own official events used, per location -- ground truth."""
    lid = {int(l): l.name for l in Location}
    out = collections.defaultdict(set)
    val = lambda x: getattr(x, 'value', x)  # noqa: E731
    d = decode_stream((ROOT / 'data/upstream_templates/RaceNetChallenges_GetChallenges.bin').read_bytes())
    for c in d['Challenges']:
        for e in c['Events']:
            for s in e['Stages']:
                t = TRACKS.get(val(s['TrackModelId']))
                if t:
                    out[lid[t['location_id']]].add(val(s['StageConditions']))
    return out


TWINS = {
    'Daytime / Overcast / Dry': (2, 38),
    'Sunset / Cloudy / Dry':    (16, 42),
    'Sunset / Cloudy / Wet':    (20, 34),
}

if __name__ == '__main__':
    lighting, encrypted = lighting_by_location()
    officials = racenet_officials()
    print(f'{len(lighting)} archives readable, {len(encrypted)} encrypted: {sorted(encrypted)}\n')
    for label, (a, b) in TWINS.items():
        print(f'=== {label}: ids {a} vs {b}')
        for loc in sorted(set(lighting) | set(officials)):
            used = officials.get(loc, set()) & {a, b}
            if not used:
                continue
            files = sorted(lighting.get(loc, set())) if loc in lighting else ['<encrypted>']
            print(f'  {loc:14} RaceNet used {sorted(used)}   ships: {files}')
        print()
