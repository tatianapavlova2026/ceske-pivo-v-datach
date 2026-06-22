"""
Vytvorenie mapping_stylov z datasetu pív.

Logika:
- kategoria1 = vždy Ale alebo Lager (podľa zhody v názve štýlu)
- kategoria2/3 = Wheat, Non-alco, Sour, Special, Dark (ak sa nájde zhoda)
- podkategoria = konkrétny podštýl z lookup tabuľky

"""

import json
import re
import pandas as pd
import unicodedata
from pathlib import Path

# ---------------------------------------------------
# LOOKUP TABUĽKY
# ---------------------------------------------------

# Kategoria1 - Ale alebo Lager
ALE_KEYWORDS = [
    "ale", "ipa", "india pale", "saison", "kolsch", "kölsch", "hefeweizen",
    "grodziskie", "dampfbier", "witbier", "altbier", "stout", "porter",
    "steinbier", "amber", "barleywine", "barley wine", "brown", "blond",
    "golden", "belgian", "biere de garde", "bière de garde", "berliner weisse",
    "dunkelweizen", "weizenbock", "lambic", "gose", "kvas", "roggenbier",
    "keptinis", "biere de champagne", "bière de champagne", "wheat ale",
    "sour ale", "cream ale", "red", "bragawd", "braggot", "raw ale",
    "milkshake", "pastry"
]

LAGER_KEYWORDS = [
    "lager", "ležák", "lezak", "výčapní", "vycapni", "výčepní", "vycepni",
    "pilsner", "pilsener", "stolní", "stolni", "marzen", "märzen",
    "kellerbier", "helles", "festbier", "bock", "steam beer",
    "dortmunder", "schwarzbier",
    "tmavý speciál", "tmavy special",
    "světlý speciál", "svetly special",
    "tmavé výčepní", "tmave vycepni",
    "polotmavé", "polotmave", "polotmavý", "polotmavy",
    "nealkoholické", "nealkoholicke",
    "pivní sekt", "pivni sekt", "radler", "pivní mix", "pivni mix",
    "india pale lager", "pale lager", "strong pale lager",
    "světlé výčepní", "svetle vycepni",
    "světlý ležák", "svetly lezak",
    "tmavý ležák", "tmavy lezak",
    "světlé pšeničné", "svetle psenicne",
    "stolní pivo", "světlé", "svetle", "tmavé", "tmave",
    "řezaný", "rezany", "řezané", "rezane"
]

ALE_KEYWORDS = [
    "ale", "ipa", "india pale ale", "saison", "kolsch", "kölsch",
    "hefeweizen", "grodziskie", "dampfbier", "witbier",
    "altbier", "stout", "porter", "steinbier", "amber", "barleywine",
    "barley wine", "brown", "blond", "golden", "belgian",
    "biere de garde", "bière de garde", "berliner weisse",
    "dunkelweizen", "weizenbock", "heller weizenbock", "dunkler weizenbock",
    "lambic", "gose", "kvas", "roggenbier",
    "keptinis", "biere de champagne", "bière de champagne", "wheat ale",
    "sour ale", "cream ale", "red", "bragawd", "braggot", "raw ale",
    "milkshake", "pastry", "american wheat", "german hefeweizen"
]

# Kategoria2/3 - Wheat, Non-alco, Sour, Special, Dark
WHEAT_KEYWORDS = [
    "pšeničné", "psenicne", "wheat", "ovesné", "ovesne", "oatmeal",
    "grodziskie", "hefeweizen", "witbier", "roggenbier", "berliner weisse"
]

NONALCO_KEYWORDS = [
    "nealkoholické", "nealkoholicke", "nealko", "non-alco", "nonalco",
    "pivní mix", "pivni mix", "radler", "bezalkoholické"
]

SOUR_KEYWORDS = [
    "sour", "kyseláč", "kysela", "kyselac", "ovocné", "ovocne", "fruit",
    "berliner weisse", "gose", "lambic", "wild ale", "brett", "lacto"
]

SPECIAL_KEYWORDS = [
    "speciál", "special", "milk", "pivní sekt", "pivni sekt", "kvas",
    "chocolate", "bière de champagne", "biere de champagne", "barleywine",
    "barley wine", "bragawd", "braggot", "pumpkin", "pastry", "imperial"
]

DARK_KEYWORDS = [
    "black", "porter", "tmavé", "tmave", "tmavý", "tmavy", "bock",
    "stout", "dunkel", "schwarzbier", "dark", "roast"
]

# Podkategorie - konkrétne hodnoty
PODKAT_LOOKUP = {
    "american pale ale": "American Pale Ale",
    "pale ale": "American Pale Ale",
    "apa": "APA",
    "ipa": "IPA",
    "india pale ale": "IPA",
    "double ipa": "IPA",
    "imperial ipa": "IPA",
    "new england ipa": "IPA",
    "session ipa": "IPA",
    "red ipa": "IPA",
    "black ipa": "IPA",
    "belgian ipa": "IPA",
    "cold ipa": "IPA",
    "saison": "Saison",
    "kolsch": "Kolsch",
    "kölsch": "Kolsch",
    "hefeweizen": "Hefeweizen",
    "grodziskie": "Grodziskie",
    "dampfbier": "Dampfbier",
    "witbier": "Belgian Witbier",
    "belgian witbier": "Belgian Witbier",
    "altbier": "Altbier",
    "stout": "Stout",
    "dry stout": "Stout",
    "imperial stout": "Stout",
    "russian imperial stout": "Stout",
    "milk stout": "Milk",
    "chocolate stout": "Chocolate Stout",
    "porter": "Porter",
    "american porter": "Porter",
    "baltic porter": "Porter",
    "imperial porter": "Porter",
    "steinbier": "Steinbier",
    "amber": "Amber",
    "amber ale": "Amber",
    "barleywine": "Barleywine",
    "barley wine": "Barleywine",
    "brown ale": "Brown",
    "brown": "Brown",
    "blond": "Blond/Golden",
    "golden ale": "Blond/Golden",
    "blond ale": "Blond/Golden",
    "golden": "Blond/Golden",
    "red ale": "Red",
    "red": "Red",
    "belgian": "Belgian",
    "belgian ale": "Belgian",
    "belgian strong ale": "Belgian",
    "quadrupel": "Belgian",
    "tripel": "Belgian",
    "dubbel": "Belgian",
    "biere de garde": "Biere de Garde",
    "bière de garde": "Biere de Garde",
    "english pale ale": "English Pale Ale",
    "berliner weisse": "Berliner Weisse",
    "dunkelweizen": "Dunkelweizen",
    "weizenbock": "Weizenbock",
    "lambic": "Lambic",
    "gose": "Gose",
    "kvas": "Kvas",
    "roggenbier": "Roggenbier",
    "keptinis": "Keptinis",
    "biere de champagne": "Biere de Champagne",
    "bière de champagne": "Biere de Champagne",
    "pilsner": "Pilsner",
    "pilsener": "Pilsner",
    "bohemian pilsner": "Pilsner",
    "marzen": "Marzen",
    "märzen": "Marzen",
    "kellerbier": "Kellerbier",
    "helles": "Helles",
    "festbier": "Festbier",
    "dunkel": "Dunkel",
    "bock": "Bock",
    "dunkler bock": "Bock",
    "maibock": "Bock",
    "doppelbock": "Bock",
    "steam beer": "Steam Beer",
    "dortmunder": "Dortmunder",
    "schwarzbier": "Schwarzbier",
    "oatmeal": "Oatmeal",
    "oatmeal stout": "Oatmeal",
    "wheat ale": "Wheat Ale",
    "american wheat": "Wheat Ale",
    "pivni mix": "Pivni mix",
    "pivní mix": "Pivni mix",
    "radler": "Radler",
    "milk": "Milk",
    "pivni sekt": "Pivni sekt",
    "pivní sekt": "Pivni sekt",
    "chocolate": "Chocolate",
    "pumpkin": "Pumpkin",
    "bragawd": "Bragawd",
    "braggot": "Bragawd",
    "sour ale": "Sour",
    "pastry sour": "Sour",
    "wild ale": "Sour",
}

# ---------------------------------------------------
# HELPER FUNKCIE
# ---------------------------------------------------

def normalize(s):
    if not s:
        return ""
    s = str(s).lower().strip()
    s = unicodedata.normalize("NFKD", s)
    return s

def obsahuje(text, keywords):
    t = normalize(text)
    for kw in keywords:
        if normalize(kw) in t:
            return True
    return False

def najdi_podkategoriu(styl_text):
    t = normalize(styl_text)
    najdene = []
    for kw, hodnota in PODKAT_LOOKUP.items():
        if normalize(kw) in t and hodnota not in najdene:
            najdene.append(hodnota)
    return ", ".join(najdene) if najdene else None

def prirad_kategorie(styl_text):
    """Vráti (kat1, kat2, kat3, podkategoria)"""
    if not styl_text or pd.isna(styl_text):
        return None, None, None, None

    # Špeciálne Ale výrazy maju prednosť pred širokými Lager keywords
    ALE_PRIORITY = [
        "weizenbock", "dunkelweizen", "hefeweizen", "witbier", "wheat ale",
        "american wheat", "german hefeweizen", "berliner weisse", "gose",
        "lambic", "dunkelweizen", "roggenbier", "grodziskie"
    ]

    t = normalize(styl_text)
    is_ale_priority = any(normalize(kw) in t for kw in ALE_PRIORITY)

    if is_ale_priority:
        kat1 = "Ale"
    elif obsahuje(styl_text, LAGER_KEYWORDS):
        kat1 = "Lager"
    elif obsahuje(styl_text, ALE_KEYWORDS):
        kat1 = "Ale"
    else:
        kat1 = None

    # Kategoria 2/3 - doplnkove
    doplnkove = []
    if obsahuje(styl_text, WHEAT_KEYWORDS):
        doplnkove.append("Wheat")
    if obsahuje(styl_text, NONALCO_KEYWORDS):
        doplnkove.append("Non-alco")
    if obsahuje(styl_text, SOUR_KEYWORDS):
        doplnkove.append("Sour")
    if obsahuje(styl_text, SPECIAL_KEYWORDS):
        doplnkove.append("Special")
    if obsahuje(styl_text, DARK_KEYWORDS):
        doplnkove.append("Dark")

    kat2 = doplnkove[0] if len(doplnkove) > 0 else None
    kat3 = doplnkove[1] if len(doplnkove) > 1 else None

    podkat = najdi_podkategoriu(styl_text)

    return kat1, kat2, kat3, podkat

# ---------------------------------------------------
# LOAD DATA
# ---------------------------------------------------

with open('/mnt/user-data/uploads/piva_KOMPLET_explode_ciste_nazvy_pivovar_matched_id_pivovaru_clean_dedup.json',
          encoding='utf-8') as f:
    data = json.load(f)

df = pd.DataFrame(data)
print(f"Načítaných pív: {len(df)}")

# ---------------------------------------------------
# APLIKUJ KATEGORIZACIU
# ---------------------------------------------------

df[['kategoria1','kategoria2','kategoria3','podkategoria']] = df['styl'].apply(
    lambda s: pd.Series(prirad_kategorie(s))
)

# ---------------------------------------------------
# POROVNAJ S POVODNYM MAPPINGOM
# ---------------------------------------------------

df_orig = pd.read_csv('/mnt/user-data/uploads/mapping_stylov.csv', encoding='utf-8')

# Spoj podla id piva
merged = df[['id','styl','kategoria1','kategoria2','kategoria3','podkategoria']].merge(
    df_orig[['id','kategoria1','kategoria2','kategoria3','podkategoria']],
    on='id', suffixes=('_new','_orig')
)

# Zhoda v kategoria1
zhoda_kat1 = (merged['kategoria1_new'] == merged['kategoria1_orig']).sum()
total = len(merged)
print(f"\nZhoda kategoria1: {zhoda_kat1}/{total} ({100*zhoda_kat1/total:.1f}%)")

zhoda_kat2 = (merged['kategoria2_new'].fillna('') == merged['kategoria2_orig'].fillna('')).sum()
print(f"Zhoda kategoria2: {zhoda_kat2}/{total} ({100*zhoda_kat2/total:.1f}%)")

# Ukazky kde sa nezhoduju
print(f"\nPríklady kde sa nezhoduje kategoria1:")
nezh = merged[merged['kategoria1_new'] != merged['kategoria1_orig']][
    ['styl','kategoria1_new','kategoria1_orig']].head(15)
print(nezh.to_string())

EOF
