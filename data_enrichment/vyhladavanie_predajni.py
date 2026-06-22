#!/usr/bin/env python3
import argparse
import csv
import http.cookiejar
import json
import re
import shutil
import socket
import ssl
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from http.cookiejar import Cookie
from pathlib import Path

# === KONFIGURÁCIA ===
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:122.0) Gecko/20100101 Firefox/122.0",
]
_ua_index = 0

TIMEOUT             = 12
PAUZA               = 0.4
PAUZA_PODSTRANKY    = 0.3
LIMIT_PODSTRANIEK   = 5

_ssl_ignore = ssl.create_default_context()
_ssl_ignore.check_hostname = False
_ssl_ignore.verify_mode    = ssl.CERT_NONE


# === SLOVNÍK ===

KORENE_PREDAJ = [
    "prodej", "prodav", "prodame", "prodavame", "vydej", "vydav",
    "stocime", "stacime", "stacirn", "naceps",
    "for sale", "buy ", "purchase", "shop", "store",
    "available", "we sell", "selling",
]

KORENE_OBAL = [
    "sud", "lah", "pet ", "petk", "litr", "keg",
    "skle", "plast",
    "bottle", "bottl", "can ", "cans ", "growler",
    "barrel", "kegs",
]

KORENE_PIVO = ["piv", "beer", "ale ", "lager", "brew"]

KORENE_PRODEJNA = [
    "prodejn", "pivotek", "obchod s pivem", "vydejn", "stacirn",
    "tap room", "taproom", "tap-room", "brewery shop",
    "brewery store", "our shop", "our store", "bottle shop",
    "bottle-shop", "off-licence", "off licence",
]

KORENE_ODBER = [
    "odber", "odnest", "odnes", "domu", "s sebou", "na cestu",
    "vyzvednut", "vyzved",
    "to go", "takeaway", "take-away", "take away",
    "to take home", "pick up", "pickup", "pick-up",
    "self-collect", "self collect",
]

KORENE_VYCAP_RESTAURACE = [
    "restaurac", "hospod", "pivnic", "hostine",
    "restaurant", "pub", "tavern", "brewpub",
    "brew pub", "tap house", "taphouse", "beer hall",
    "pivobar", "pivni bar", "pivní bar",
]

KORENE_VYCAP_CEPOVANIE = [
    "cepuj", "cepovan", " cepu", "tocim", "tocime",
    "tankov", "vycep",
    "on tap", "on draught", "on draft", "draft beer",
    "draught beer", "tap beer", "tank beer",
]

KORENE_RESTAURACE_OSTATNE = [
    "jidelni", "obed", "vecere", "obcerstv",
    "rezervace stol",
    "menu", "lunch", "dinner", "reservation",
    "book a table", "booking",
    "nase provozovny", "nase pobocky",
]

KORENE_KAM_NA = [
    "kam na pivo", "kde se napit", "kam zajit",
    "kam na nase pivo", "kde nas najdete na pivo",
    "kde nase pivo cepujem", "kde nase pivo capuje",
    "where to drink", "where to find our beer",
    "find our beer at",
]

KORENE_ZAKOUPIT    = ["zakoupit", "koupit", "kupte"]
SLOVA_U_PIVOVARU   = [
    "u nas", "v pivovaru", "v sidle", "na pivovare",
    "primo v pivovaru", "primo u nas", "primo v pivu",
    "v nasem pivovaru", "v nasi pivnici",
]

KORENE_PO_DOMLUVE = [
    "po domluve", "po dohode", "po predchozim objednani",
    "na zavolani", "na telefonu", "kontaktujte nas",
    "by appointment", "by arrangement",
]

KORENE_ESHOP = [
    "objedn", "rozvoz", "dorucujeme", "kuryr", "posilame",
    "posleme", "doruc",
    "order ", "ordering", "delivery", "ship ", "shipping",
]

# ── NOVÉ V4: Prevádzková doba ─────────────────────────────────────────────────
KORENE_PREVADZKA = [
    "provozni doba", "provozní doba",
    "oteviraci doba", "otevírací doba",
    "opening hours", "hours of operation",
    "otevreno", "otevřeno",
    "navstivte nas", "navštivte nás",
    "jsme otevreni", "jsme otevřeni",
]

# Dni v týždni (celé slová) – signál otváracia doba
DNI_RE = re.compile(
    r'\b(pondel[ií]|uterý|úterý|streda|středa|čtvrtek|ctvrtek|'
    r'pátek|patek|sobota|neděle|nedele|'
    r'monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b',
    re.IGNORECASE
)

# Časy – rozšírený pattern (s medzerami aj bez)
OTVARACIA_DOBA_RE = re.compile(
    r'\b(?:po|ut|st|ct|pa|so|ne|mo|tu|we|th|fr|sa|su)\s*[-–]\s*'
    r'(?:po|ut|st|ct|pa|so|ne|mo|tu|we|th|fr|sa|su)\b'
    r'|\b\d{1,2}\s*[:.]\s*\d{2}\s*[-–]\s*\d{1,2}\s*[:.]\s*\d{2}\b'
    r'|\b\d{1,2}\s*[-–]\s*\d{1,2}\s*(?:hod|h\b)',
    re.IGNORECASE
)
# ─────────────────────────────────────────────────────────────────────────────

SILNE_FRAZY_PRODEJNA = [
    "podnikova prodejna", "firemni prodejna",
    "pivoteka", "pivni obchod",
    "pivo s sebou", "pivo na cestu", "pivo domu",
    "stacirna piva",
    "v nasi prodejne", "do nasi prodejny", "nase prodejna",
    "kde nas najdete", "navstivte nas",
    "muzete koupit", "muzete zakoupit", "muzete si zakoupit",
    "prodavame piva", "prodej piva",
    "odber piva", "odnest domu",
    "stacame do petlahvi", "stacame do sudu",
    "kde koupit nase pivo", "kde se da koupit",
    "nase piva najdete", "nase piva si muzete koupit",
    "beer to go", "beer to take home", "take home beer",
    "buy our beer", "buy beer", "purchase beer", "buy beers",
    "our beers are available", "available for purchase",
    "fill your growler", "growler fills",
    "open for takeaway", "available to take away",
    "visit our shop", "visit our store", "visit our taproom",
    "available at our brewery", "directly from the brewery",
]

SLOVA_OBEC = [
    "obecni urad", "obecniho uradu", "mestsky urad", "mestskeho uradu",
    "starosta obce", "starostka obce", "mistostarosta",
    "obecni zastupitelstvo", "zastupitelstvo obce", "zastupitelstvo mesta",
    "samosprava obce", "samosprava mesta", "uredni deska", "uredni hodiny",
    "matrika", "ohlasovna pobytu", "podatelna obce", "podatelna mesta",
    "vyhlaska obce", "vyhlaska mesta", "rozpocet obce", "rozpocet mesta",
    "kronika obce", "kronika mesta", "historie obce",
]

PODSTRANKY = [
    "/kontakt", "/kontakty",
    "/prodej", "/prodej-piva", "/prodejna",
    "/eshop", "/e-shop", "/obchod",
    "/o-nas", "/onas", "/o-pivovaru", "/about",
    "/restaurace", "/restauracia", "/hospoda", "/pivnice",
    "/sluzby", "/services",
    "/cenik",
    "/kam-na-pivo", "/kam-na-nase-pivo", "/kde-koupit", "/kde-najdete",
    "/distribuce", "/where-to-find", "/where-to-buy", "/find-us",
    "/provozovny", "/pobocky",
    "/provozni-doba", "/oteviraci-doba", "/opening-hours",
]

FB_DOMENY = ["facebook.com", "m.facebook.com", "fb.com", "fb.me"]


# === HELPER FUNKCIE ===

def dalsi_ua():
    global _ua_index
    ua = USER_AGENTS[_ua_index % len(USER_AGENTS)]
    _ua_index += 1
    return ua


def je_facebook(url):
    if not url:
        return False
    try:
        host = urllib.parse.urlparse(
            url if url.startswith(("http", "//")) else "http://" + url
        ).netloc.lower()
        host = host[4:] if host.startswith("www.") else host
        return any(host == d or host.endswith("." + d) for d in FB_DOMENY)
    except Exception:
        return False


def normalizuj_text(text):
    text = text.lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = re.sub(r'\s+', ' ', text)
    return text


def vycisti_html(text):
    text = re.sub(r'<script[^>]*>.*?</script>', ' ', text, flags=re.S | re.I)
    text = re.sub(r'<style[^>]*>.*?</style>',  ' ', text, flags=re.S | re.I)
    text = re.sub(r'<[^>]+>', ' ', text)
    return text


def najdi_pozicie(text, koren):
    pozicie, start = [], 0
    while True:
        idx = text.find(koren, start)
        if idx == -1:
            break
        pozicie.append(idx)
        start = idx + 1
    return pozicie


def kolko_blizkostnych_zhod(text, korene_a, korene_b, vzdialenost=80):
    pozicie_a = []
    for k in korene_a:
        pozicie_a.extend(najdi_pozicie(text, k))
    pozicie_b = []
    for k in korene_b:
        pozicie_b.extend(najdi_pozicie(text, k))
    pocet = 0
    for pa in pozicie_a:
        for pb in pozicie_b:
            if abs(pa - pb) <= vzdialenost:
                pocet += 1
                break
    return pocet


def ma_blizko(text, korene_a, korene_b, vzdialenost=80):
    return kolko_blizkostnych_zhod(text, korene_a, korene_b, vzdialenost) > 0


# === AGE GATE BYPASS ===

def _vytvor_age_jar(domain):
    jar = http.cookiejar.CookieJar()
    domains = [domain]
    if domain.startswith('www.'):
        domains.extend([domain[4:], '.' + domain[4:]])
    else:
        domains.append('.' + domain)
    age_cookies = [
        ('age_verified','1'), ('ageVerified','true'),
        ('age_confirmed','1'), ('age_check','1'),
        ('age','18'), ('isAdult','1'), ('over18','1'),
        ('ageGate','1'), ('ac','1'),
    ]
    for name, value in age_cookies:
        for d in domains:
            try:
                c = Cookie(
                    version=0, name=name, value=value,
                    port=None, port_specified=False,
                    domain=d, domain_specified=True,
                    domain_initial_dot=d.startswith('.'),
                    path='/', path_specified=True,
                    secure=False, expires=None, discard=False,
                    comment=None, comment_url=None, rest={},
                )
                jar.set_cookie(c)
            except Exception:
                pass
    return jar


def detekuj_age_gate(text):
    if not text:
        return False
    tl = text.lower()
    phrases = [
        "bylo vám", "bylo vam", "18 let", "18 years",
        "of legal age", "ověření věku", "overeni veku",
        "agegate", "age-gate", "age verification",
        "jste starší 18", "jste starsi 18",
    ]
    return any(p in tl for p in phrases) and len(text) < 5000


def najdi_ano_link(html_text):
    patterns = [
        r'<a[^>]+href="([^"]*)"[^>]*>(?:[^<]*?)(?:Ano|ANO|Yes|YES|Souhlas|Vstoupit|Pokra[cč]ovat|Continue|Enter|Potvrd)',
        r'href="([^"]*)"[^>]*>\s*Ano\s*<',
        r'href="([^"]*)"[^>]*>\s*ANO\s*<',
        r'href="([^"]*ac=1[^"]*)"',
        r'href="([^"]*age=ok[^"]*)"',
    ]
    for p in patterns:
        m = re.search(p, html_text, re.IGNORECASE)
        if m:
            return m.group(1)
    return None


def http_get(url, timeout=TIMEOUT):
    if not url:
        return None, None, ""
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    parsed = urllib.parse.urlparse(url)
    domain = parsed.netloc
    jar    = _vytvor_age_jar(domain)

    def vytvor_opener(ssl_ignore=False):
        handlers = [urllib.request.HTTPCookieProcessor(jar)]
        if ssl_ignore:
            handlers.append(urllib.request.HTTPSHandler(context=_ssl_ignore))
        opener = urllib.request.build_opener(*handlers)
        opener.addheaders = [
            ('User-Agent',      dalsi_ua()),
            ('Accept',          'text/html,application/xhtml+xml,*/*;q=0.8'),
            ('Accept-Language', 'cs-CZ,cs;q=0.9'),
            ('Accept-Encoding', 'identity'),
        ]
        return opener

    def stiahni(target_url, opener):
        try:
            resp    = opener.open(target_url, timeout=timeout)
            data    = resp.read(2_000_000)
            charset = resp.headers.get_content_charset() or "utf-8"
            try:
                text = data.decode(charset, errors="replace")
            except Exception:
                text = data.decode("utf-8", errors="replace")
            return resp.status, resp.geturl(), text
        except urllib.error.HTTPError as e:
            return e.code, target_url, ""
        except Exception:
            return None, target_url, ""

    opener = vytvor_opener(ssl_ignore=False)
    status, final_url, text = stiahni(url, opener)

    if not text and url.startswith("https://"):
        opener = vytvor_opener(ssl_ignore=True)
        status, final_url, text = stiahni(url, opener)

    if not text and url.startswith("https://"):
        opener = vytvor_opener(ssl_ignore=False)
        status, final_url, text = stiahni("http://" + url[8:], opener)

    if not text:
        return status, final_url, ""

    if detekuj_age_gate(text):
        ano_link = najdi_ano_link(text)
        if ano_link:
            ano_url = urllib.parse.urljoin(final_url, ano_link)
            s2, f2, t2 = stiahni(ano_url, opener)
            if t2 and not detekuj_age_gate(t2):
                return s2, f2, t2
        sep       = '&' if '?' in url else '?'
        s4, f4, t4 = stiahni(url + sep + 'ac=1&age=ok', opener)
        if t4 and not detekuj_age_gate(t4):
            return s4, f4, t4

    return status, final_url, text


# === DETEKCIE ===

def detekuj_obecny_web(text_norm):
    najdene = [w for w in SLOVA_OBEC if w in text_norm]
    return len(najdene) >= 2, najdene


def detekuj_prevadzku(text_norm):
    """
    Vráti (skore_p, skore_v, dovod) ak stránka obsahuje prevádzkovú dobu.
    Kombinácia: kľúčové slovo prevadzka + časy + dni = silný signál.
    """
    ma_prevadzku_kw = any(k in text_norm for k in KORENE_PREVADZKA)
    ma_casy         = bool(OTVARACIA_DOBA_RE.search(text_norm))
    ma_dni          = bool(DNI_RE.search(text_norm))

    skore_p, skore_v, dovody = 0, 0, []

    if ma_prevadzku_kw and ma_casy:
        skore_v += 4
        skore_p += 2
        dovody.append("provozni_doba+casy(+4v,+2p)")
    elif ma_prevadzku_kw and ma_dni:
        skore_v += 3
        skore_p += 1
        dovody.append("provozni_doba+dni(+3v,+1p)")
    elif ma_casy and ma_dni:
        # Časy + dni bez explicitného kľúčového slova - slabší signál
        skore_v += 2
        skore_p += 1
        dovody.append("casy+dni(+2v,+1p)")
    elif ma_casy:
        skore_v += 1
        dovody.append("casy(+1v)")

    return skore_p, skore_v, dovody


def detekuj_predajne(html_text, mesto_pivovaru):
    text_raw = vycisti_html(html_text)
    text     = normalizuj_text(text_raw)
    mesto_norm = normalizuj_text(mesto_pivovaru) if mesto_pivovaru else ""

    skore_p, dovody_p = 0, []
    skore_v, dovody_v = 0, []

    # === PRODEJNA ===

    # 1. Silné frázy
    najdene_frazy = [f for f in SILNE_FRAZY_PRODEJNA if f in text]
    if najdene_frazy:
        body = min(len(najdene_frazy) * 3, 9)
        skore_p += body
        dovody_p.append(f"frázy:{','.join(najdene_frazy[:3])}(+{body})")

    # 2. PREDAJ + PIVO/OBAL blízko
    pocet = kolko_blizkostnych_zhod(text, KORENE_PREDAJ,
                                     KORENE_PIVO + KORENE_OBAL, 60)
    if pocet > 0:
        body = min(pocet * 2, 6)
        skore_p += body
        dovody_p.append(f"predaj+pivo:{pocet}x(+{body})")

    # 3. PRODEJNA koreň
    if any(k in text for k in KORENE_PRODEJNA):
        skore_p += 2
        dovody_p.append(f"prodejna({[k for k in KORENE_PRODEJNA if k in text][0]},+2)")

    # 4. ODBER + PIVO
    pocet = kolko_blizkostnych_zhod(text, KORENE_ODBER, KORENE_PIVO, 60)
    if pocet > 0:
        body = min(pocet, 3)
        skore_p += body
        dovody_p.append(f"odber+pivo:{pocet}x(+{body})")

    # 5. ZAKOUPIT + kontext
    pozicie_zak = []
    for k in KORENE_ZAKOUPIT:
        pozicie_zak.extend(najdi_pozicie(text, k))
    if pozicie_zak:
        kontextove = list(SLOVA_U_PIVOVARU)
        if mesto_norm and len(mesto_norm) >= 4:
            kontextove.append(mesto_norm)
        ok_zak = 0
        for pz in pozicie_zak:
            for kt in kontextove:
                if any(abs(pz - pk) <= 80 for pk in najdi_pozicie(text, kt)):
                    ok_zak += 1
                    break
        if ok_zak > 0:
            body = min(ok_zak * 2, 4)
            skore_p += body
            dovody_p.append(f"zakoupit+u_nas:{ok_zak}x(+{body})")

    # 6. PO DOMLUVE
    pocet_pd = sum(text.count(k) for k in KORENE_PO_DOMLUVE if k in text)
    if pocet_pd > 0:
        ma_obal  = any(k in text for k in KORENE_OBAL)
        ma_mesto = mesto_norm and len(mesto_norm) >= 4 and mesto_norm in text
        if ma_obal or ma_mesto:
            skore_p += 2
            dovody_p.append("po_domluve+kontext(+2)")

    # 7. Typy obalov
    najdene_obaly = [k for k in KORENE_OBAL if k in text]
    pocet_obal    = len(najdene_obaly)
    if pocet_obal >= 3:
        skore_p += 2
        dovody_p.append("obaly:3+typov(+2)")
    elif pocet_obal >= 2:
        skore_p += 1
        dovody_p.append("obaly:2typy(+1)")

    # 8. Otváracia doba + obaly
    if pocet_obal >= 1 and OTVARACIA_DOBA_RE.search(text):
        skore_p += 1
        dovody_p.append("oteviraci_doba+obal(+1)")

    # === VYCAP ===

    def ma_mesto_blizko(slova_korene, vzdialenost=100):
        if not mesto_norm or len(mesto_norm) < 4:
            return False
        pozicie_slov = []
        for k in slova_korene:
            pozicie_slov.extend(najdi_pozicie(text, k))
        pozicie_mesta = najdi_pozicie(text, mesto_norm)
        return any(
            abs(ps - pm) <= vzdialenost
            for ps in pozicie_slov
            for pm in pozicie_mesta
        )

    # 1. RESTAURACE/HOSPODA
    najdene_rest = [k for k in KORENE_VYCAP_RESTAURACE if k in text]
    if najdene_rest:
        if ma_mesto_blizko(KORENE_VYCAP_RESTAURACE):
            skore_v += 4
            dovody_v.append(f"restaurace+mesto({najdene_rest[0]},+4)")
        else:
            skore_v += 2
            dovody_v.append(f"restaurace({najdene_rest[0]},+2)")

    # 2. CEPOVANIE
    najdene_cep = [k for k in KORENE_VYCAP_CEPOVANIE if k in text]
    if najdene_cep:
        if ma_mesto_blizko(KORENE_VYCAP_CEPOVANIE):
            skore_v += 4
            dovody_v.append(f"cepovani+mesto({najdene_cep[0].strip()},+4)")
        else:
            skore_v += 2
            dovody_v.append(f"cepovani({najdene_cep[0].strip()},+2)")

    # 3. KAM NA PIVO
    if any(k in text for k in KORENE_KAM_NA):
        if ma_mesto_blizko(KORENE_KAM_NA):
            skore_v += 3
            skore_p += 1
            dovody_v.append("kam_na_pivo+mesto(+3)")
            dovody_p.append("kam_na_pivo+mesto(+1)")

    # 4. RESTAURACE_OSTATNE
    najdene_rest_ost = [k for k in KORENE_RESTAURACE_OSTATNE if k in text]
    if len(najdene_rest_ost) >= 2:
        skore_v += 2
        dovody_v.append(f"menu:{','.join(najdene_rest_ost[:2])}(+2)")

    # === NOVÉ V4: PREVÁDZKOVÁ DOBA ===
    sp_prev, sv_prev, dovody_prev = detekuj_prevadzku(text)
    if sp_prev > 0:
        skore_p += sp_prev
        dovody_p.extend(dovody_prev)
    if sv_prev > 0:
        skore_v += sv_prev
        dovody_v.extend(dovody_prev)

    # === ESHOP DETEKCIA ===
    pocet_eshop        = sum(1 for k in KORENE_ESHOP if k in text)
    ma_fyzicku_predajnu = (
        len(najdene_frazy) > 0
        or kolko_blizkostnych_zhod(text, KORENE_PREDAJ, KORENE_OBAL, 60) > 0
        or any(k in text for k in KORENE_PRODEJNA)
        or any(k in text for k in SLOVA_U_PIVOVARU)
        or any(k in text for k in KORENE_PO_DOMLUVE)
        or sp_prev > 0  # prevádzková doba = fyzická prítomnosť
    )
    je_len_eshop = (pocet_eshop >= 2 and not ma_fyzicku_predajnu and skore_p < 3)

    return {
        "skore_p":    skore_p,
        "skore_v":    skore_v,
        "dovody_p":   dovody_p,
        "dovody_v":   dovody_v,
        "text_norm":  text,
        "je_len_eshop": je_len_eshop,
    }


# === VYHODNOTENIE ===

def vyhodnot_finalne(skore_p, skore_v, je_len_eshop, typ_pivovaru):
    typ_lower = typ_pivovaru.lower() if typ_pivovaru else ""

    # Vycap
    if "restaur" in typ_lower:
        prodejna_vycap = True
    elif any(s in typ_lower for s in [
        "uzavren","uzavřen","pripravov","připravov","letajic","létajíc","domovar"
    ]):
        prodejna_vycap = False
    elif skore_v >= 4:
        prodejna_vycap = True
    elif skore_v == 0:
        prodejna_vycap = False
    else:
        prodejna_vycap = ""

    # Prodejna
    if any(s in typ_lower for s in [
        "uzavren","uzavřen","pripravov","připravov","domovar"
    ]):
        prodejna = False
    elif je_len_eshop:
        prodejna = "len e-shop"
    elif skore_p >= 4:
        prodejna = True
    elif skore_p >= 2:
        prodejna = True
    elif skore_p == 0:
        prodejna = False
    else:
        prodejna = ""

    return prodejna, prodejna_vycap


# === SPRACOVANIE PIVOVARU ===

def spracuj_pivovar(p):
    typ       = p.get('typ', '')
    typ_lower = typ.lower()
    web       = (p.get('web') or '').strip()
    mesto     = p.get('mesto', '')

    def auto_result(dov):
        res = {'prodejna': False, 'prodejna_vycap': False,
               'prodejna_dovod': dov, 'vycap_dovod': dov,
               'skore_p': 0, 'skore_v': 0}
        return res

    # Auto-pravidlá podľa typu
    if any(s in typ_lower for s in ["uzavren","uzavřen"]):
        return auto_result(f'auto: typ={typ}')
    if any(s in typ_lower for s in ["pripravov","připravov"]):
        return auto_result(f'auto: typ={typ}')
    if typ_lower == "domovar":
        return auto_result(f'auto: typ={typ}')

    # FB profil
    if web and je_facebook(web):
        res = {'prodejna': "Facebook profil",
               'prodejna_dovod': 'web je FB profil',
               'skore_p': 0, 'skore_v': 0}
        if "letajic" in typ_lower or "létajíc" in typ_lower:
            res.update({'prodejna_vycap': False, 'vycap_dovod': f'auto: typ={typ}'})
        elif "restaur" in typ_lower:
            res.update({'prodejna_vycap': True, 'vycap_dovod': f'auto: typ={typ}'})
        else:
            res.update({'prodejna_vycap': '', 'vycap_dovod': 'FB - bez detekcie'})
        return res

    # Bez webu
    if not web:
        res = {'prodejna': '', 'prodejna_dovod': 'bez webu',
               'skore_p': 0, 'skore_v': 0}
        if "letajic" in typ_lower or "létajíc" in typ_lower:
            res.update({'prodejna_vycap': False, 'vycap_dovod': f'auto: typ={typ}, bez webu'})
        elif "restaur" in typ_lower:
            res.update({'prodejna_vycap': True, 'vycap_dovod': f'auto: typ={typ}'})
        else:
            res.update({'prodejna_vycap': '', 'vycap_dovod': 'bez webu'})
        return res

    # Stiahnutie hlavnej stránky
    code, final_url, text = http_get(web)
    if not text:
        res = {'prodejna': '', 'prodejna_dovod': f'web nedostupný (HTTP {code})',
               'skore_p': 0, 'skore_v': 0}
        if "letajic" in typ_lower or "létajíc" in typ_lower:
            res.update({'prodejna_vycap': False, 'vycap_dovod': f'auto: typ={typ}'})
        elif "restaur" in typ_lower:
            res.update({'prodejna_vycap': True, 'vycap_dovod': f'auto: typ={typ}'})
        else:
            res.update({'prodejna_vycap': '', 'vycap_dovod': 'web nedostupný'})
        return res

    # Detekcia
    main = detekuj_predajne(text, mesto)

    # Obecný web
    is_obec, obec_slova = detekuj_obecny_web(main['text_norm'])
    if is_obec and main['skore_p'] < 3:
        return {'prodejna': "web obce", 'prodejna_vycap': False,
                'prodejna_dovod': f'web obce: {",".join(obec_slova[:3])}',
                'vycap_dovod': 'web obce', 'skore_p': 0, 'skore_v': 0}

    skore_p_total = main['skore_p']
    skore_v_total = main['skore_v']
    dovody_p_all  = list(main['dovody_p'])
    dovody_v_all  = list(main['dovody_v'])
    je_len_eshop  = main['je_len_eshop']

    # Podstránky (ak nie je istota)
    if skore_p_total < 4 or skore_v_total < 4:
        try:
            parsed_u = urllib.parse.urlparse(final_url)
            base     = f"{parsed_u.scheme}://{parsed_u.netloc}"
        except Exception:
            base = web.rstrip('/')

        linky_z_textu = re.findall(r'href=["\']([^"\']+)["\']', text)
        relevantne, seen = [], set()
        for lnk in linky_z_textu:
            lnk_low = lnk.lower()
            for ps in PODSTRANKY:
                if ps in lnk_low:
                    absurl = (lnk if lnk.startswith('http')
                              else base + lnk if lnk.startswith('/')
                              else base + '/' + lnk)
                    if absurl not in seen:
                        seen.add(absurl)
                        relevantne.append(absurl)
                    break

        for ps in PODSTRANKY:
            absurl = base + ps
            if absurl not in seen:
                seen.add(absurl)
                relevantne.append(absurl)

        navstivene = 0
        for sub_url in relevantne:
            if navstivene >= LIMIT_PODSTRANIEK:
                break
            navstivene += 1
            time.sleep(PAUZA_PODSTRANKY)

            _, _, sub_text = http_get(sub_url)
            if not sub_text:
                continue

            sub = detekuj_predajne(sub_text, mesto)
            path_short = urllib.parse.urlparse(sub_url).path or '/'

            if sub['skore_p'] > 0:
                pridane = min(sub['skore_p'], 3)
                skore_p_total += pridane
                if sub['dovody_p']:
                    dovody_p_all.append(f"{path_short}:{sub['dovody_p'][0]}")

            if sub['skore_v'] > 0:
                pridane = min(sub['skore_v'], 3)
                skore_v_total += pridane
                if sub['dovody_v']:
                    dovody_v_all.append(f"{path_short}:{sub['dovody_v'][0]}")

            if sub['je_len_eshop'] and not je_len_eshop:
                je_len_eshop = True
            if sub['skore_p'] >= 3 and not sub['je_len_eshop']:
                je_len_eshop = False

    prodejna, prodejna_vycap = vyhodnot_finalne(
        skore_p_total, skore_v_total, je_len_eshop, typ
    )

    if "restaur" in typ_lower and not any('typ=' in d for d in dovody_v_all):
        dovody_v_all.insert(0, f'auto: typ={typ}')
    if "letajic" in typ_lower or "létajíc" in typ_lower:
        dovody_v_all.insert(0, f'auto: typ={typ}')

    return {
        'prodejna':       prodejna,
        'prodejna_vycap': prodejna_vycap,
        'prodejna_dovod': '; '.join(dovody_p_all) if dovody_p_all else 'žádné',
        'vycap_dovod':    '; '.join(dovody_v_all) if dovody_v_all else 'žádné',
        'skore_p':        skore_p_total,
        'skore_v':        skore_v_total,
    }


# === MAIN ===

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("vstup",           help="JSON s pivovarmi")
    ap.add_argument("--start",  type=int, default=0)
    ap.add_argument("--limit",  type=int, default=None)
    ap.add_argument("--no-backup", action="store_true")
    args = ap.parse_args()

    vstup = Path(args.vstup)
    if not vstup.exists():
        print(f"Súbor {vstup} neexistuje.", file=sys.stderr)
        sys.exit(1)

    vystup   = vstup.with_name(vstup.stem + "_v4.json")
    csv_path = vstup.with_name(vstup.stem + "_v4.csv")

    if not args.no_backup:
        backup = vstup.with_name(vstup.stem + "_backup.json")
        shutil.copy2(vstup, backup)
        print(f"✓ Backup: {backup.name}")

    with vstup.open(encoding='utf-8') as f:
        pivovary = json.load(f)

    KEY_NAZEV = 'nazev_pivovaru' if pivovary and 'nazev_pivovaru' in pivovary[0] \
                else 'nazov_pivovaru'

    for p in pivovary:
        p.setdefault('prodejna',       '')
        p.setdefault('prodejna_vycap', '')
        p.setdefault('prodejna_dovod', '')
        p.setdefault('vycap_dovod',    '')
        p.setdefault('skore_p',        '')
        p.setdefault('skore_v',        '')

    end = (len(pivovary) if args.limit is None
           else min(len(pivovary), args.start + args.limit))
    print(f"Načítaných {len(pivovary)}, spracujem {args.start+1}–{end}\n")

    pocty = {'auto_pravidla':0,'fb_profil':0,'web_obce':0,
             'len_eshop':0,'aktualizovane':0}

    def zapis_priebezne():
        with vystup.open('w', encoding='utf-8') as f:
            json.dump(pivovary, f, ensure_ascii=False, indent=2)

    for i in range(args.start, end):
        p     = pivovary[i]
        nazev = p.get(KEY_NAZEV, '?')
        typ   = p.get('typ', '')

        new = spracuj_pivovar(p)

        dovod = new.get('prodejna_dovod', '')
        if 'auto: typ=' in dovod:        pocty['auto_pravidla'] += 1; znak = '🔧'
        elif new.get('prodejna') == 'Facebook profil': pocty['fb_profil'] += 1; znak = '📘'
        elif new.get('prodejna') == 'web obce':        pocty['web_obce'] += 1;  znak = '🏛'
        elif new.get('prodejna') == 'len e-shop':      pocty['len_eshop'] += 1; znak = '🛒'
        else:                                          znak = '🌐'

        for k in ('prodejna','prodejna_vycap','prodejna_dovod',
                  'vycap_dovod','skore_p','skore_v'):
            if k in new:
                p[k] = new[k]
        pocty['aktualizovane'] += 1

        prod_v = new.get('prodejna','')
        vyc_v  = new.get('prodejna_vycap','')
        ps = '✓' if prod_v is True else ('✗' if prod_v is False else str(prod_v)[:12] if prod_v else '?')
        vs = '✓' if vyc_v  is True else ('✗' if vyc_v  is False else '?')
        sp = new.get('skore_p', 0)
        sv = new.get('skore_v', 0)
        print(f"[{i+1}/{end}] {znak} {nazev[:32]:32s} ({typ[:18]:18s}) "
              f"P={ps:6s}({sp:>2}) V={vs:2s}({sv:>2})")

        time.sleep(PAUZA)

        if (i + 1) % 25 == 0:
            zapis_priebezne()

    zapis_priebezne()

    polia = list(pivovary[0].keys())
    with csv_path.open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=polia, delimiter=';')
        w.writeheader()
        for p in pivovary:
            row = {}
            for k in polia:
                v = p.get(k, '')
                row[k] = ('true' if v is True else 'false' if v is False else v)
            w.writerow(row)

    from collections import Counter
    prod_c = Counter()
    vyc_c  = Counter()
    for p in pivovary[args.start:end]:
        v = p.get('prodejna','')
        prod_c['True'  if v is True  else
               'False' if v is False else
               '(prázdne)' if v == '' else str(v)] += 1
        v = p.get('prodejna_vycap','')
        vyc_c ['True'  if v is True  else
               'False' if v is False else
               '(prázdne)' if v == '' else str(v)] += 1

    print(f"\n=== ŠTATISTIKA ===")
    print(f"  Auto-pravidlá: {pocty['auto_pravidla']}")
    print(f"  FB profil:     {pocty['fb_profil']}")
    print(f"  Web obce:      {pocty['web_obce']}")
    print(f"  Len e-shop:    {pocty['len_eshop']}")
    print(f"\n=== PRODEJNA ===")
    for k, v in prod_c.most_common(): print(f"  {k}: {v}")
    print(f"\n=== VYCAP ===")
    for k, v in vyc_c.most_common():  print(f"  {k}: {v}")

    print(f"\n→ {vystup}")
    print(f"→ {csv_path}")


if __name__ == "__main__":
    main()
