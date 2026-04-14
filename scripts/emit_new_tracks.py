"""Emit Python enum + metadata code for new TrackModelIds captured by
tt_smart_probe, filtering out IDs already present in game_data.py."""
import json
import re
from collections import defaultdict
from pathlib import Path

with open('runtime/discovery/tt_smart_results.json', 'rb') as f:
    NEW = json.loads(f.read().decode('latin-1'))
GD = Path('dr2server/game_data.py').read_text(encoding='utf-8')

# Existing TrackModelIds: only the Track enum class section.
track_section = GD[GD.index('class Track'):GD.index('class VehicleClass')]
existing_ids = set()
for m in re.finditer(r'^\s+([A-Z_0-9]+)\s*=\s*(\d+)\s*$', track_section, re.MULTILINE):
    existing_ids.add(int(m.group(2)))

LOC_MAP = {
    'JAMSA': 'FINLAND',
    'BAUMHOLDER': 'GERMANY',
    'ARGOLIS': 'GREECE',
    'LECZNA COUNTY': 'POLAND',
    'MONTE CARLO': 'MONTE_CARLO',
    ': RIBADELLES': 'SPAIN',
    'VARMLAND': 'SWEDEN',
    'POWYS': 'WALES',
    'PERTH AND KINROSS': 'SCOTLAND',
    'CATAMARCA PROVINCE': 'ARGENTINA',
    'MONARO': 'AUSTRALIA',
    'HAWKES BAY': 'NEW_ZEALAND',
    'NEW ENGLAND': 'NEW_ENGLAND',
}

# OCR-mangled -> canonical display names (with accents restored where known)
CANON = {
    'Kontinjarvi': 'Kontinj\u00e4rvi',
    'Hamelahti': 'H\u00e4melahti',
    'Kailajairvi': 'Kailaj\u00e4rvi',
    'Jyrkysjarvi': 'Jyrkysj\u00e4rvi',
    'Naarajarvi': 'Naaraj\u00e4rvi',
    'Paskuri': 'Paskuri',
    'Iso Oksjarvi': 'Iso Oksj\u00e4rvi',
    'Jarvenkyla': 'J\u00e4rvenkyl\u00e4',
    'Frauenberg': 'Frauenberg',
    'Kreuzungsring Reverse': 'Kreuzungsring Reverse',
    'Kreuzungsring': 'Kreuzungsring',
    'Waldabstieg': 'Waldabstieg',
    'Ruschberg': 'Ruschberg',
    'Verbundsring': 'Verbundsring',
    'Innerer Feld-Sprint (umgekehrt)': 'Innerer Feld-Sprint (umgekehrt)',
    'Verbundsring Reverse': 'Verbundsring Reverse',
    'Anodou Farmakas': 'Anodou Farmakas',
    'Kathodo Leontiou': 'Kathodo Leontiou',
    'Pomona Ekrixi': 'Pomona Ekrixi',
    'Koryfi Dafni': 'Koryfi Dafni',
    'Perasma Platani': 'Perasma Platani',
    'Tsiristra Th\ufffda': 'Tsiristra Th\u00e9a',
    'Pedines Epidaxi': 'Pedines Epidaxi',
    'Abies Koilada': 'Abies Koilada',
    'Ypsona tou Dasos': 'Ypsona tou Dasos',
    'Borysik': 'Borysik',
    'J\ufffdzefin': 'J\u00f3zefin',
    'Pra d\ufffdAlart': "Pra d'Alart",
    'Col de Turini D\ufffdpart': 'Col de Turini D\u00e9part',
    'Gordolon - Courte mont\ufffde': 'Gordolon - Courte mont\u00e9e',
    'Col de Turini - Sprint en descente': 'Col de Turini - Sprint en descente',
    'Col de Turini sprint en Mont\ufffde': 'Col de Turini sprint en Mont\u00e9e',
    'Col de Turini - Descente': 'Col de Turini - Descente',
    'Vall\ufffde descendante': 'Vall\u00e9e descendante',
    'Route de Turini': 'Route de Turini',
    'Col de Turini - D\ufffdpart en descente': 'Col de Turini - D\u00e9part en descente',
    'Approche du Col de Turini - Mont\ufffde': 'Approche du Col de Turini - Mont\u00e9e',
    'Route de Turini Descente': 'Route de Turini Descente',
    'Route de Turini Mont\ufffde': 'Route de Turini Mont\u00e9e',
    'Vifiedos dentro del valle Parra': 'Vi\u00f1edos dentro del valle Parra',
    'Centenera': 'Centenera',
    'Vifiedos Dardenya': 'Vi\u00f1edos Dardenya',
    'Vifiedos Dardenya inversa': 'Vi\u00f1edos Dardenya inversa',
    'Ranshysater': 'R\u00e4mshyttan',
    'Norraskoga': 'Norraskoga',
    'Algsj\ufffdn Sprint': '\u00c4lgsj\u00f6n Sprint',
    'Stor-jangen Sprint': 'Stor-jangen Sprint',
    'Skogsrallyt': 'Skogsrallyt',
    'Hamra': 'Hamra',
    'Lysvik': 'Lysvik',
    'Elgsjon': 'Elgsj\u00f6n',
    'Bjorklangen': 'Bj\u00f6rklangen',
    'Ostra Hinnsj\ufffdn': '\u00d6stra Hinnsj\u00f6n',
    'Algsj\ufffdn': '\u00c4lgsj\u00f6n',
    'Geufron Forest': 'Geufron Forest',
    'Bidno Moorland Reverse': 'Bidno Moorland Reverse',
    'Bronfelen': 'Bronfelen',
    'Fferm Wynt': 'Fferm Wynt',
    'Dyffryn Afon': 'Dyffryn Afon',
    'South Morningside': 'South Morningside',
    'South Morningside Reverse': 'South Morningside Reverse',
    'Rosebank Farm': 'Rosebank Farm',
    'Old Butterstone Muir Reverse': 'Old Butterstone Muir Reverse',
    'Newhouse Bridge Reverse': 'Newhouse Bridge Reverse',
    'Glencastle Farm': 'Glencastle Farm',
    'Annbank Station': 'Annbank Station',
    'Glencastle Farm Reverse': 'Glencastle Farm Reverse',
}


def ident(name: str) -> str:
    repl = {
        '\u00e4': 'a', '\u00c4': 'A', '\u00f6': 'o', '\u00d6': 'O',
        '\u00fc': 'u', '\u00dc': 'U', '\u00e9': 'e', '\u00c9': 'E',
        '\u00e8': 'e', '\u00f1': 'n', '\u00d1': 'N', '\u00e5': 'a',
        '\u00c5': 'A', '\u00ed': 'i', '\u00e1': 'a', '\u00f3': 'o',
    }
    for k, v in repl.items():
        name = name.replace(k, v)
    name = re.sub(r"[^\w\s]", ' ', name)
    name = re.sub(r'\s+', '_', name.strip())
    return name.upper()


new_tracks = []
for loc, stages in NEW.items():
    for stage_name, tm in stages:
        if tm is None or tm in existing_ids:
            continue
        canonical = CANON.get(stage_name, stage_name)
        new_tracks.append((LOC_MAP[loc], tm, ident(canonical), canonical))

grouped = defaultdict(list)
for loc, tm, i, disp in new_tracks:
    grouped[loc].append((tm, i, disp))

print('# ENUM ADDITIONS')
for loc in sorted(grouped):
    print(f'\n    # {loc}')
    for tm, i, disp in sorted(grouped[loc]):
        print(f'    {i:45s} = {tm}')
print(f'\n# Total new: {len(new_tracks)}\n')

print('# META ADDITIONS')
for loc in sorted(grouped):
    for tm, i, disp in sorted(grouped[loc]):
        print(f'    Track.{i}: {{"display_name": "{disp}", "location": Location.{loc}, "length_km": 0.0}},')
