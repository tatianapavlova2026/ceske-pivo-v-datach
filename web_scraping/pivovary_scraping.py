import json
import os
import re
from bs4 import BeautifulSoup

# Konfigurace souborů
FILE_PATH = 'kraj.html'
OUTPUT_JSON = 'pivovary_kraj.json'

def parse_info_string(info_str):
    """Pomocná funkce pro rozsekání textového bloku na jednotlivé údaje."""
    data = {
        "typ": "Neuvedeno",
        "mesto": "Neuvedeno",
        "kraj": "Neuvedeno",
        "adresa": "Neuvedeno",
        "zalozeno": "Neuvedeno"
    }
    
    # 1. Extrakce Typu (text mezi 'Typ:' a 'Město:')
    typ_match = re.search(r'Typ:\s*(.*?)\s*Město:', info_str)
    if typ_match:
        data["typ"] = typ_match.group(1).strip()
    
    # 2. Extrakce Města a Kraje
    mesto_kraj_match = re.search(r'Město:\s*(.*?)\s*Adresa:', info_str)
    if mesto_kraj_match:
        mesto_raw = mesto_kraj_match.group(1).strip()
        if "(" in mesto_raw:
            data["mesto"] = mesto_raw.split("(")[0].strip()
            # Získáme text v závorce a odstraníme zbytečné info
            kraj_part = mesto_raw.split("(")[1]
            data["kraj"] = kraj_part.split(",")[0].replace(")", "").strip()
        else:
            data["mesto"] = mesto_raw

    # 3. Extrakce Adresy (vše mezi Adresa: a Založeno:)
    adresa_match = re.search(r'Adresa:\s*(.*?)\s*Založeno:', info_str)
    if adresa_match:
        data["adresa"] = adresa_match.group(1).strip()

    # 4. VYLEPŠENÁ Extrakce Roku založení
    # Hledá slovo 'Založeno', přeskočí jakékoli znaky a vezme první 4 číslice
    zalozeno_match = re.search(r'Založeno:.*?(\d{4})', info_str)
    if zalozeno_match:
        data["zalozeno"] = zalozeno_match.group(1)
        
    return data

def run_extraction():
    if not os.path.exists(FILE_PATH):
        print(f"CHYBA: Soubor {FILE_PATH} nebyl nalezen!")
        return

    print(f"Načítám soubor {FILE_PATH}...")
    with open(FILE_PATH, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f.read(), 'html.parser')

    # Seznam frází, které nechceme jako názvy pivovarů
    zakazane_texty = [
        "více informací o pivovaru »", 
        "více informací", 
        "pivovar", 
        "zpět", 
        "piva", 
        "pivovary",
        "mapa"
    ]

    results = []
    seen_names = set()

    # Najdeme všechny odkazy vedoucí na detaily pivovarů
    all_links = soup.find_all('a', href=True)
    
    for link in all_links:
        if '/pivovar/' in link['href']:
            nazev = link.get_text(strip=True)
            
            # Základní filtr názvů
            if not nazev or len(nazev) < 3 or nazev.lower() in zakazane_texty:
                continue
            
            # Prevence duplicit
            if nazev in seen_names:
                continue
            
            # Najdeme rodičovský prvek (řádek v seznamu)
            parent = link.find_parent(['li', 'tr', 'div', 'td'])
            if parent:
                raw_text = parent.get_text(" ", strip=True)
                
                # Pokud řádek neobsahuje "Typ:", pravděpodobně to není hlavní řádek
                if "Typ:" not in raw_text:
                    continue

                # Zpracujeme textový blok
                parsed_fields = parse_info_string(raw_text)
                
                # Sestavíme záznam
                entry = {
                    "nazov_pivovaru": nazev,
                    "krajina": "Česká republika",
                    **parsed_fields
                }
                
                results.append(entry)
                seen_names.add(nazev)

    # Uložení do JSONu
    with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=4)
    
    print("-" * 40)
    print(f"ÚSPĚCH! Celkem vytěženo {len(results)} záznamů.")
    print(f"Data uložena do: {OUTPUT_JSON}")
    print("-" * 40)

if __name__ == "__main__":
    run_extraction()
