#!/usr/bin/env python3
import argparse
import csv
import json
import re
import socket
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:122.0) Gecko/20100101 Firefox/122.0",
]
_ua_index = 0

TIMEOUT = 12
PAUZA = 0.4

FB_DOMENY = {"facebook.com", "m.facebook.com", "fb.com", "fb.me"}
INE_SOCIAL = {"instagram.com", "twitter.com", "x.com", "linkedin.com", "tiktok.com"}

# Slová ktoré indikujú stránku obce/mesta
SLOVA_OBEC = [
    "obecní úřad", "obecního úřadu", "městský úřad", "městského úřadu",
    "starosta obce", "starostka obce", "místostarosta",
    "obecní zastupitelstvo", "zastupitelstvo obce", "zastupitelstvo města",
    "samospráva obce", "samospráva města", "úřední deska", "úřední hodiny",
    "matrika", "ohlašovna pobytu", "podatelna obce", "podatelna města",
    "vyhláška obce", "vyhláška města", "rozpočet obce", "rozpočet města",
    "kronika obce", "kronika města", "historie obce",
]

# Indikátory parkovanej domény
SLOVA_PARKOVANA = [
    "domain is for sale", "doména je na prodej", "this domain is parked",
    "buy this domain", "sedo.com", "godaddy.com/domains",
    "this website is for sale", "domain for sale", "prodej domény",
    "domena na prodej", "domena je na prodej",
]


def dalsi_ua():
    global _ua_index
    ua = USER_AGENTS[_ua_index % len(USER_AGENTS)]
    _ua_index += 1
    return ua


def odstran_diakritiku(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn"
    )


def normalizuj(s: str) -> str:
    s = odstran_diakritiku(s.lower())
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def domena(url: str) -> str:
    try:
        host = urllib.parse.urlparse(url).netloc.lower()
        return host[4:] if host.startswith("www.") else host
    except Exception:
        return ""


def je_facebook(url: str) -> bool:
    d = domena(url)
    return any(d == fd or d.endswith("." + fd) for fd in FB_DOMENY)


def je_iny_social(url: str) -> bool:
    d = domena(url)
    return any(d == sd or d.endswith("." + sd) for sd in INE_SOCIAL)


def http_get(url: str, timeout: int = TIMEOUT) -> tuple:
    """Vráti (status, final_url, html_text)."""
    if not url:
        return None, None, "__ERR__:prázdne URL"
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        headers = {
            "User-Agent": dalsi_ua(),
            "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
            "Accept-Language": "cs-CZ,cs;q=0.9,en;q=0.5",
            "Accept-Encoding": "identity",
            "Connection": "close",
        }
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read(800_000)
            charset = resp.headers.get_content_charset() or "utf-8"
            try:
                text = data.decode(charset, errors="replace")
            except Exception:
                text = data.decode("utf-8", errors="replace")
            return resp.status, resp.geturl(), text
    except urllib.error.HTTPError as e:
        return e.code, url, f"__ERR__:HTTP {e.code}"
    except urllib.error.URLError as e:
        return None, url, f"__ERR__:URL chyba: {e.reason}"
    except socket.timeout:
        return None, url, "__ERR__:timeout"
    except Exception as e:
        return None, url, f"__ERR__:{type(e).__name__}: {e}"


def extract_meta(text: str, prop: str) -> str:
    """Vyhľadá <meta property="..." content="..."> alebo <meta name="..." content="...">."""
    # og:title, og:description, twitter:title, ...
    patterns = [
        rf'<meta[^>]+property=["\']{re.escape(prop)}["\'][^>]+content=["\']([^"\']+)["\']',
        rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']{re.escape(prop)}["\']',
        rf'<meta[^>]+name=["\']{re.escape(prop)}["\'][^>]+content=["\']([^"\']+)["\']',
    ]
    for p in patterns:
        m = re.search(p, text, re.I)
        if m:
            return m.group(1).strip()
    return ""


def extract_title(text: str) -> str:
    m = re.search(r"<title[^>]*>(.*?)</title>", text, re.I | re.DOTALL)
    return m.group(1).strip() if m else ""


def overit_facebook(url: str, nazov: str) -> tuple:
    """
    Overí FB stránku — či existuje, a ako veľmi súvisí s pivovarom.
    Vracia (status, final_url, dovod, skore).
    """
    code, final, text = http_get(url)
    if code is None:
        return "fb_chyba", url, text.replace("__ERR__:", ""), 0
    if code == 404:
        return "fb_404", url, "FB stránka neexistuje (404)", 0
    if code >= 400:
        return "fb_chyba", url, f"FB HTTP {code}", 0

    # FB často redirectuje na login - ale meta tagy v HTML stále sú prístupné
    # Vytiahneme og:title, og:description, twitter:title, title
    og_title = extract_meta(text, "og:title")
    og_desc = extract_meta(text, "og:description")
    tw_title = extract_meta(text, "twitter:title")
    title = extract_title(text)
    
    vsetok_text = " ".join([og_title, og_desc, tw_title, title]).lower()
    vsetok_norm = normalizuj(vsetok_text)
    
    # Detekcia "Sign in to Facebook" / "Log in" - ak nemáme reálny obsah
    if not og_title and not og_desc and not tw_title:
        # Žiadne meta tagy - asi vyžaduje login
        if "log in to facebook" in text.lower() or "přihlásit se na facebook" in text.lower():
            return "fb_login_required", final or url, "FB vyžaduje login pre zobrazenie", 0
        return "fb_bez_metadat", final or url, "FB stránka bez verejných meta tagov", 0

    # Skóre - či meta tagy obsahujú názov pivovaru
    nazov_norm = normalizuj(nazov)
    klucove = [s for s in nazov_norm.split() if len(s) > 3]
    zhody = [s for s in klucove if s in vsetok_norm]
    
    skore = 0
    dovody = []
    if zhody:
        skore += 3
        dovody.append(f"názov v FB: {','.join(zhody)}")
    
    if any(w in vsetok_text for w in ("pivovar", "pivo", "brewery", "beer")):
        skore += 1
        dovody.append("'pivo/pivovar' v FB")
    
    if og_title:
        dovody.append(f"og:title='{og_title[:50]}'")

    if skore >= 3:
        return "fb_ok", final or url, "; ".join(dovody), skore
    if skore >= 1:
        return "fb_ok_slabe", final or url, "; ".join(dovody), skore
    return "fb_neoveritelne", final or url, f"og:title='{og_title[:50]}', skóre {skore}", skore


def overit_obecny_web(url: str, pivovar: dict) -> tuple:
    """
    Overí klasický web (nie FB).
    Vracia (status, final_url, dovod, skore).
    """
    code, final, text = http_get(url)
    if code is None:
        return "http_chyba", url, text.replace("__ERR__:", ""), 0
    if code == 404:
        return "http_404", url, "stránka neexistuje (404)", 0
    if code >= 500:
        return "http_5xx", url, f"server error {code}", 0
    if code >= 400:
        return "http_chyba", url, f"HTTP {code}", 0
    
    text_lower = text.lower()
    text_norm = normalizuj(text_lower[:120_000])

    # Parkovaná doména?
    if any(ind in text_lower for ind in SLOVA_PARKOVANA):
        return "parkovana", final or url, "doména parkovaná / na predaj", 0
    
    # Stránka obce/mesta?
    obec_matches = [w for w in SLOVA_OBEC if w in text_lower]
    if len(obec_matches) >= 2:
        # Aj tak môže byť pivovar - skúsime ďalej, ale označíme príznak
        skore_obec = len(obec_matches)
    else:
        skore_obec = 0

    # Skórujeme obsah
    nazov_norm = normalizuj(pivovar.get('nazov_pivovaru', ''))
    obch_norm = normalizuj(pivovar.get('ico_obchodne_meno', ''))
    mesto_norm = normalizuj(pivovar.get('mesto', ''))
    ico = (pivovar.get('ico') or '').strip()

    skore = 0
    dovody = []
    
    # IČO - silný signál
    if ico and ico in text:
        skore += 5
        dovody.append(f"IČO {ico}")
    
    # Názov pivovaru
    klucove = [s for s in nazov_norm.split() if len(s) > 3]
    nazov_zhody = [s for s in klucove if s in text_norm]
    if nazov_zhody:
        skore += 3
        dovody.append(f"názov: {','.join(nazov_zhody)}")
    
    # Obchodné meno
    if obch_norm:
        obch_klucove = [s for s in obch_norm.split() if len(s) > 3 and s != "pivovar"]
        obch_zhody = [s for s in obch_klucove if s in text_norm]
        if obch_zhody:
            skore += 2
            dovody.append(f"obch.meno: {','.join(obch_zhody)}")
    
    # Pivo/pivovar
    if any(w in text_lower for w in ("pivovar", "pivo", "brewery", "beer", "pivní")):
        skore += 1
        dovody.append("'pivo/pivovar'")
    
    # Mesto
    if mesto_norm and mesto_norm in text_norm:
        skore += 1
        dovody.append(f"mesto: {mesto_norm}")

    # Vyhodnotenie
    if skore_obec >= 2 and skore < 3:
        # Veľa indícií že je to obec, málo že je to pivovar
        return "vyzera_ako_obec", final or url, \
               f"obec indikátory: {len(obec_matches)} ('{', '.join(obec_matches[:3])}'), pivovar skóre: {skore}", \
               skore
    
    if skore >= 4:
        return "ok", final or url, "; ".join(dovody), skore
    if skore >= 2:
        return "ok_slabe", final or url, "; ".join(dovody), skore
    if skore >= 1:
        return "ok_velmi_slabe", final or url, "; ".join(dovody) or "len 'pivo' v texte", skore
    return "nerelevantne", final or url, f"skóre {skore} - žiadne kľúčové slovo", skore


def overit_web(url: str, pivovar: dict) -> tuple:
    """Hlavná funkcia. Vráti (status, final_url, dovod, skore)."""
    if not url or not url.strip():
        return "prazdny", "", "prázdne URL", 0
    
    nazov = pivovar.get('nazov_pivovaru', '')
    
    if je_facebook(url):
        return overit_facebook(url, nazov)
    
    if je_iny_social(url):
        # Instagram/Twitter - skúsime overiť ako bežný web ale označíme
        status, final, dovod, skore = overit_obecny_web(url, pivovar)
        return f"social_{status}", final, dovod, skore
    
    return overit_obecny_web(url, pivovar)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("vstup", help="JSON s pivovarmi")
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    vstup = Path(args.vstup)
    if not vstup.exists():
        print(f"Súbor {vstup} neexistuje.", file=sys.stderr)
        sys.exit(1)

    out_dir = vstup.parent
    out_json = out_dir / "pivovary_weby_overene.json"
    out_csv = out_dir / "pivovary_weby_overene.csv"
    out_problemy = out_dir / "pivovary_weby_problemy.csv"
    out_obec = out_dir / "pivovary_weby_obec.csv"

    with vstup.open(encoding="utf-8") as f:
        pivovary = json.load(f)

    # Pridať nové polia
    for p in pivovary:
        p.setdefault('web_status', '')
        p.setdefault('web_dovod', '')
        p.setdefault('web_skore', '')
        p.setdefault('web_final', '')

    end = len(pivovary) if args.limit is None else min(len(pivovary), args.start + args.limit)
    print(f"Načítaných {len(pivovary)} pivovarov, overujem {args.start+1}–{end}.\n")

    def zapis_priebezne():
        with out_json.open("w", encoding="utf-8") as f:
            json.dump(pivovary, f, ensure_ascii=False, indent=2)

    for i in range(args.start, end):
        p = pivovary[i]
        nazov = p.get('nazov_pivovaru', '')
        web = (p.get('web') or '').strip()
        
        if not web:
            p['web_status'] = 'prazdny'
            p['web_dovod'] = 'pivovar nemá web'
            p['web_skore'] = '0'
            p['web_final'] = ''
            print(f"[{i+1}/{end}] {nazov} – bez webu, preskočené")
            continue
        
        print(f"[{i+1}/{end}] {nazov}", flush=True)
        print(f"           web: {web}")
        
        status, final, dovod, skore = overit_web(web, p)
        p['web_status'] = status
        p['web_dovod'] = dovod
        p['web_skore'] = str(skore)
        p['web_final'] = final or ''
        
        print(f"           → {status} (skóre {skore}): {dovod}")
        time.sleep(PAUZA)

        if (i + 1) % 20 == 0:
            zapis_priebezne()

    # Finálne zápisy
    zapis_priebezne()

    polia = list(pivovary[0].keys())
    with out_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=polia, delimiter=";")
        w.writeheader()
        for p in pivovary:
            w.writerow({k: p.get(k, '') for k in polia})

    # Problémové
    PROBLEMOVE_STATUSY = {
        'http_404', 'http_chyba', 'http_5xx', 'parkovana', 'fb_404',
        'fb_chyba', 'fb_login_required', 'fb_bez_metadat', 'fb_neoveritelne',
        'nerelevantne', 'ok_velmi_slabe',
    }
    problemy = [p for p in pivovary[args.start:end] if p['web_status'] in PROBLEMOVE_STATUSY]
    with out_problemy.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=polia, delimiter=";")
        w.writeheader()
        for p in problemy:
            w.writerow({k: p.get(k, '') for k in polia})

    obec = [p for p in pivovary[args.start:end] if p['web_status'] == 'vyzera_ako_obec']
    with out_obec.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=polia, delimiter=";")
        w.writeheader()
        for p in obec:
            w.writerow({k: p.get(k, '') for k in polia})

    # Súhrn
    from collections import Counter
    statusy = Counter(p['web_status'] for p in pivovary[args.start:end])
    print("\n--- SÚHRN ---")
    for s, c in sorted(statusy.items(), key=lambda x: -x[1]):
        print(f"  {s:25s} {c}")
    print(f"\nVýstupy:")
    print(f"  {out_json.name}")
    print(f"  {out_csv.name}")
    print(f"  {out_problemy.name}  (problémové: {len(problemy)})")
    print(f"  {out_obec.name}      (obec/mesto: {len(obec)})")


if __name__ == "__main__":
    main()