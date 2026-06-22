# !/usr/bin/env python3
import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path


def kombinacie_stylov(pivo):
    """
    Z jedného piva vytiahne všetky kombinácie kategória+podkategória.
    Vracia set reťazcov napr. {"Ale:IPA", "7-Dark:Stout", "3-Wheat"}
    """
    styly = set()

    kategorie = [
        pivo.get('kategoria1'),
        pivo.get('kategoria2'),
        pivo.get('kategoria3'),
    ]
    kategorie = [k for k in kategorie if k]  # odstráni None

    podkat_raw = pivo.get('podkategoria') or ''

    # Podkategória môže byť "IPA, Stout" – rozdelíme
    podkategorie = [p.strip() for p in podkat_raw.split(',') if p.strip()] \
                   if podkat_raw else []

    for kat in kategorie:
        if podkategorie:
            for pod in podkategorie:
                styly.add(f"{kat}:{pod}")
        else:
            styly.add(kat)

    return styly


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vstup", default="mapping_stylov.json",
                    help="Vstupný JSON súbor (default: mapping_stylov.json)")
    args = ap.parse_args()

    vstup_path = Path(args.vstup)
    vystup_json = Path('diverzita_pivovarov.json')
    vystup_csv  = Path('diverzita_pivovarov.csv')

    with vstup_path.open(encoding='utf-8') as f:
        piva = json.load(f)

    print(f"Načítaných pív: {len(piva)}")

    # Agregácia na úrovni pivovar_id
    # Pivovar môže mať pivovar_id_1 aj pivovar_id_2
    pivovar_styly   = defaultdict(set)   # id → set kombinácií
    pivovar_nazov   = {}                 # id → názov pivovaru

    for pivo in piva:
        pid1 = pivo.get('pivovar_id_1')
        pid2 = pivo.get('pivovar_id_2')
        nazov = pivo.get('pivovar', '')

        komb = kombinacie_stylov(pivo)

        for pid in [pid1, pid2]:
            if pid:
                pivovar_styly[pid].update(komb)
                if pid not in pivovar_nazov:
                    pivovar_nazov[pid] = nazov

    print(f"Unikátnych pivovarov: {len(pivovar_styly)}")

    # Zostavenie výsledku
    vysledok = []
    for pid, styly in sorted(pivovar_styly.items()):
        # Rozdeľ kombinácie späť na kategórie a podkategórie
        kat_set = set()
        for s in styly:
            if ':' in s:
                kat_set.add(s.split(':')[0])
            else:
                kat_set.add(s)

        vysledok.append({
            'pivovar_id':          pid,
            'nazev_pivovaru':      pivovar_nazov.get(pid, ''),
            'pocet_stylov':        len(styly),
            'pocet_kategorii':     len(kat_set),
            'styly_zoznam':        ', '.join(sorted(styly)),
            'kategorie_zoznam':    ', '.join(sorted(kat_set)),
        })

    # Zoraď podľa diverzity (zostupne)
    vysledok.sort(key=lambda x: x['pocet_stylov'], reverse=True)

    # Výpis top 20
    print(f"\n{'='*65}")
    print(f"Top 20 najdiverzifikovanejších pivovarov:")
    print(f"{'='*65}")
    print(f"{'ID':>5}  {'Pivovar':<35} {'Štýly':>6} {'Kat':>4}")
    print(f"{'-'*65}")
    for r in vysledok[:20]:
        print(f"{r['pivovar_id']:>5}  {r['nazev_pivovaru'][:35]:<35} "
              f"{r['pocet_stylov']:>6}  {r['pocet_kategorii']:>3}")

    # Štatistika
    print(f"\n{'='*65}")
    print(f"Štatistika diverzity:")
    pocty = [r['pocet_stylov'] for r in vysledok]
    print(f"  Priemer:  {sum(pocty)/len(pocty):.1f} štýlov/pivovar")
    print(f"  Medián:   {sorted(pocty)[len(pocty)//2]} štýlov")
    print(f"  Max:      {max(pocty)} štýlov")
    print(f"  Min:      {min(pocty)} štýlov")

    from collections import Counter
    dist = Counter(r['pocet_stylov'] for r in vysledok)
    print(f"\nDistribúcia (štýlov → počet pivovarov):")
    for k in sorted(dist.keys())[:15]:
        print(f"  {k:>3} štýlov: {dist[k]:>4} pivovarov")

    # Uloženie
    with vystup_json.open('w', encoding='utf-8') as f:
        json.dump(vysledok, f, ensure_ascii=False, indent=2)

    polia = ['pivovar_id', 'nazev_pivovaru', 'pocet_stylov',
             'pocet_kategorii', 'styly_zoznam', 'kategorie_zoznam']
    with vystup_csv.open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=polia, delimiter=';')
        w.writeheader()
        w.writerows(vysledok)

    print(f"\n✓ HOTOVO")
    print(f"→ {vystup_json}")
    print(f"→ {vystup_csv}")


if __name__ == '__main__':
    main()
