import os
from bs4 import BeautifulSoup
import json
import re

# Názov výsledného súboru
OUTPUT_JSON = 'vsetky_piva.json'

def parse_pivnici_html():
    piva_list = []
    html_files = [f for f in os.listdir('.') if f.endswith('.html')]
    
    if not html_files:
        print(" Chyba: Nenašiel som žiadne .html súbory!")
        return

    print(f" Spracovávam české pivovary a adresy...")
    print("-" * 40)

    for file_name in html_files:
        try:
            with open(file_name, 'r', encoding='utf-8') as f:
                soup = BeautifulSoup(f.read(), 'html.parser')

            items = soup.find_all('div', class_='item')
            
            for item in items:
                h2 = item.find('h2')
                if not h2: continue
                nazov_piva = h2.get_text(strip=True)

                details = item.find('div', class_='details')
                if not details: continue
                
                def get_val(pattern):
                    label = details.find('span', class_='label', string=re.compile(pattern, re.I))
                    if label and label.parent:
                        return label.parent.get_text(" ", strip=True).replace(label.get_text(strip=True), "").strip()
                    return "Neuvedené"

                # --- LOGIKA PRE PIVOVARY A ADRESY ---
                pivovar_raw = get_val("Spolupráce")
                if pivovar_raw == "Neuvedené":
                    pivovar_raw = get_val("Skupina pivovarů")
                if pivovar_raw == "Neuvedené":
                    pivovar_raw = get_val("Pivovar")

                # 1. Názvy pivovarov oddelené čiarkou (bez adries)
                pivovar_clean = pivovar_raw.replace('\n', ', ')
                pivovar_names = re.sub(r'\s*\(.*?\)', '', pivovar_clean).strip()
                pivovar_names = re.sub(r'\s*,\s*', ', ', pivovar_names).strip(', ')
                
                # 2. Hľadanie ČESKEJ adresy (mesto, kraj)
                mesto = "Neuvedené"
                kraj = "Neuvedené"
                
                # Nájdeme všetky zátvorky (lokality)
                lokality = re.findall(r'\((.*?)\)', pivovar_raw)
                
                found_czech = False
                for lok in lokality:
                    if "Česká republika" in lok:
                        casti = [c.strip() for c in lok.split(',')]
                        if len(casti) >= 1: mesto = casti[0]
                        if len(casti) >= 2: kraj = casti[1]
                        found_czech = True
                        break # Našli sme českú adresu, končíme hľadanie
                
                # Ak sme nenašli explicitne českú, vezmeme prvú dostupnú
                if not found_czech and lokality:
                    casti = [c.strip() for c in lokality[0].split(',')]
                    if len(casti) >= 1: mesto = casti[0]
                    if len(casti) >= 2: kraj = casti[1]

                # --- OSTATNÉ ÚDAJE ---
                def clean_num(txt, full_decimal=True):
                    if txt == "Neuvedené": return "Neuvedené"
                    m = re.search(r'(\d+[,.]?\d*)' if full_decimal else r'(\d+)', txt)
                    if m: return m.group(1).replace(',', '.').rstrip('.')
                    return "Neuvedené"

                entry = {
                    "nazov_piva": nazov_piva,
                    "pivovar": pivovar_names,
                    "mesto": mesto,
                    "kraj": kraj,
                    "hodnotenie": item.find('span', class_='rating').get_text(strip=True).replace(',', '.') if item.find('span', class_='rating') else "0",
                    "sezonnost": get_val("Sezónní"),
                    "skupina_piv": get_val("Skupina piv"),
                    "styl": get_val("Pivní styl"),
                    "stupnovitost": clean_num(get_val("Stupňovitost")),
                    "alkohol_percento": clean_num(get_val("Obsah alkoholu")),
                    "horkost_IBU": clean_num(get_val("Hořkost"), False)
                }

                if not any(p['nazov_piva'] == nazov_piva and p['pivovar'] == pivovar_names for p in piva_list):
                    piva_list.append(entry)

        except Exception as e:
            print(f" Chyba v {file_name}: {e}")

    with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(piva_list, f, ensure_ascii=False, indent=4)

    print("-" * 40)
    print(f" Hotovo! Vyfiltrované české adresy sú v: {OUTPUT_JSON}")

if __name__ == "__main__":
    parse_pivnici_html()
