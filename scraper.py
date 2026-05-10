import requests, sqlite3, json, hashlib, re, time, os
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from urllib.parse import urljoin

_status = {"running": False, "progress": 0, "current": "", "total": 0, "done": 0, "log": []}

def get_status():
    return dict(_status)

def _log(msg, level="info"):
    t = datetime.now().strftime("%H:%M:%S")
    _status["log"] = (_status["log"] + [{"t": t, "msg": msg, "level": level}])[-80:]
    print(f"[{t}] {msg}")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "fr-FR,fr;q=0.9",
}

SOURCES = [
    {"id":"coinafrique","name":"CoinAfrique CI","base":"https://ci.coinafrique.com","urls":["https://ci.coinafrique.com/annonces/immobilier"],"selectors":{"items":".card-annonce, article, .ad-card","title":"h2, h3, .title","price":".price, .prix","location":".location, .address","link":"a","image":"img","description":"p, .description"}},
    {"id":"expat","name":"Expat-Dakar CI","base":"https://www.expat-dakar.com","urls":["https://www.expat-dakar.com/immobilier/cote-d-ivoire"],"selectors":{"items":".listing-card, article, .offer-item","title":"h2, h3","price":".price, .listing-price","location":".location, .listing-location","link":"a","image":"img","description":"p"}},
    {"id":"jumia","name":"Jumia House CI","base":"https://house.jumia.ci","urls":["https://house.jumia.ci/fr/a-louer/","https://house.jumia.ci/fr/a-vendre/"],"selectors":{"items":".property-card, article, .listing","title":"h2, h3","price":".price","location":".location","link":"a","image":"img","description":"p"}},
    {"id":"jiji","name":"Jiji CI","base":"https://jiji.ci","urls":["https://jiji.ci/immobilier"],"selectors":{"items":"article, .advert-item, .b-list-advert","title":"h3, .advert-title","price":".price-obj, .qa-advert-price","location":".advert-region, .b-list-advert__region","link":"a","image":"img","description":"p"}},
    {"id":"tayc","name":"Tayc Immobilier","base":"https://tayc-immo.ci","urls":["https://tayc-immo.ci/annonces"],"selectors":{"items":".property, article, .listing","title":"h2, h3","price":".price, .prix","location":".location","link":"a","image":"img","description":"p"}},
    {"id":"tonton","name":"Tonton Immo","base":"https://www.tontonimmo.com","urls":["https://www.tontonimmo.com/annonces"],"selectors":{"items":".property-item, article","title":"h2, h3","price":".price","location":".location","link":"a","image":"img","description":"p"}},
    {"id":"luxury","name":"Luxury Home Abidjan","base":"https://luxuryhomeabidjan.com","urls":["https://luxuryhomeabidjan.com/proprietes"],"selectors":{"items":".property, article","title":"h2, h3","price":".price","location":".location","link":"a","image":"img","description":"p"}},
    {"id":"kalimba","name":"Kalimba Immobilier","base":"https://www.kalimbaimmobilier.com","urls":["https://www.kalimbaimmobilier.com/annonces"],"selectors":{"items":".property, article, .card","title":"h2, h3","price":".price","location":".location","link":"a","image":"img","description":"p"}},
    {"id":"agentiz","name":"Agentiz CI","base":"https://ci.agentiz.com","urls":["https://ci.agentiz.com/annonces"],"selectors":{"items":".property-card, article","title":"h2, h3","price":".price","location":".location","link":"a","image":"img","description":"p"}},
    {"id":"yapgi","name":"Yapgi Immobilier","base":"https://yapgi-immobilier.com","urls":["https://yapgi-immobilier.com/annonces"],"selectors":{"items":".property, article","title":"h2, h3","price":".price","location":".location","link":"a","image":"img","description":"p"}},
    {"id":"brokers","name":"Brokers Afrika","base":"https://brokersafrika.com","urls":["https://brokersafrika.com/annonces"],"selectors":{"items":".property, article","title":"h2, h3","price":".price","location":".location","link":"a","image":"img","description":"p"}},
    {"id":"isis","name":"Isis Immobilier","base":"https://isis-immobilier.com","urls":["https://isis-immobilier.com/annonces"],"selectors":{"items":".property, article","title":"h2, h3","price":".price","location":".location","link":"a","image":"img","description":"p"}},
    {"id":"officiel","name":"Officiel Immobilier","base":"https://officielimmobilier.net","urls":["https://officielimmobilier.net/annonces"],"selectors":{"items":".property, article","title":"h2, h3","price":".price","location":".location","link":"a","image":"img","description":"p"}},
    {"id":"ha","name":"HA Properties","base":"https://ha-properties.com","urls":["https://ha-properties.com/annonces"],"selectors":{"items":".property, article","title":"h2, h3","price":".price","location":".location","link":"a","image":"img","description":"p"}},
    {"id":"aici","name":"AICI.ci","base":"https://aici.ci","urls":["https://aici.ci/annonces"],"selectors":{"items":".property, article","title":"h2, h3","price":".price","location":".location","link":"a","image":"img","description":"p"}},
    {"id":"mdimmo","name":"MD Immo CI","base":"https://mdimmo-ci.com","urls":["https://mdimmo-ci.com/annonces"],"selectors":{"items":".property, article","title":"h2, h3","price":".price","location":".location","link":"a","image":"img","description":"p"}},
    {"id":"sandra","name":"Sandrak Immo","base":"https://sandrakimmo.com","urls":["https://sandrakimmo.com/annonces"],"selectors":{"items":".property, article","title":"h2, h3","price":".price","location":".location","link":"a","image":"img","description":"p"}},
    {"id":"kle","name":"KLE Immobilier","base":"https://kleimmobilier.com","urls":["https://kleimmobilier.com/annonces"],"selectors":{"items":".property, article","title":"h2, h3","price":".price","location":".location","link":"a","image":"img","description":"p"}},
]

def extract_price(text):
    if not text: return 0, ""
    clean = re.sub(r"[^\d]", "", text)
    val = int(clean) if clean else 0
    if "million" in text.lower(): val *= 1_000_000
    elif val > 0 and val < 1000 and "000" not in text: val *= 1_000
    return val, text.strip()

def detect_transaction(text, url=""):
    t = (text + " " + url).lower()
    if any(w in t for w in ["vente","à vendre","achat","acheter"]): return "Vente"
    if any(w in t for w in ["location","louer","à louer","loyer"]): return "Location"
    return "Vente"

def detect_type(text):
    t = text.lower()
    types = [("Villa",["villa"]),("Appartement",["appartement","appart"]),("Studio",["studio"]),("Duplex",["duplex"]),("Terrain",["terrain","parcelle"]),("Immeuble",["immeuble"]),("Bureau",["bureau"]),("Local commercial",["local commercial","boutique"]),("Magasin",["magasin"]),("Entrepôt",["entrepôt","hangar"]),("Chambre",["chambre"]),("Maison",["maison"])]
    for typ, kws in types:
        if any(kw in t for kw in kws): return typ
    return "Appartement"

def detect_zone(text):
    ZONES = {"Cocody":["cocody"],"Riviera Golf":["riviera golf","golf"],"Riviera":["riviera"],"2 Plateaux":["2 plateaux","deux plateaux"],"Angré":["angré","angre"],"Marcory":["marcory"],"Zone 4":["zone 4","zone4"],"Biétry":["biétry","bietry"],"Plateau":["plateau"],"Treichville":["treichville"],"Yopougon":["yopougon"],"Koumassi":["koumassi"],"Adjamé":["adjamé","adjame"],"Abobo":["abobo"],"Bingerville":["bingerville"],"Grand-Bassam":["bassam"],"Djibi":["djibi"],"Palmeraie":["palmeraie"]}
    t = text.lower()
    for zone, kws in ZONES.items():
        if any(kw in t for kw in kws): return zone
    return "Abidjan"

def make_id(url, title):
    return hashlib.md5(f"{url}{title}".encode()).hexdigest()[:16]

def fetch_page(url, timeout=20):
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        r.raise_for_status()
        r.encoding = r.apparent_encoding or "utf-8"
        return r.text
    except Exception as e:
        _log(f"Erreur fetch {url}: {e}", "err")
        return None

def fetch_page_playwright(url):
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
            page = browser.new_page(extra_http_headers={"User-Agent": HEADERS["User-Agent"]})
            page.goto(url, timeout=30000, wait_until="domcontentloaded")
            time.sleep(2)
            html = page.content()
            browser.close()
            return html
    except Exception as e:
        _log(f"Playwright erreur: {e}", "err")
        return fetch_page(url)

def parse_annonces(html, source, config):
    if not html: return []
    soup = BeautifulSoup(html, "html.parser")
    sel = source["selectors"]
    items = []
    for selector in sel["items"].split(", "):
        items = soup.select(selector.strip())
        if items: break
    if not items:
        items = soup.select("article, .card, .property, .listing")
    _log(f"  {len(items)} elements sur {source['name']}", "info")
    annonces = []
    for item in items[:30]:
        try:
            title = ""
            for s in sel["title"].split(", "):
                el = item.select_one(s.strip())
                if el and el.get_text(strip=True): title = el.get_text(strip=True); break
            prix_txt = ""
            for s in sel["price"].split(", "):
                el = item.select_one(s.strip())
                if el and el.get_text(strip=True): prix_txt = el.get_text(strip=True); break
            loc_txt = ""
            for s in sel["location"].split(", "):
                el = item.select_one(s.strip())
                if el and el.get_text(strip=True): loc_txt = el.get_text(strip=True); break
            link = ""
            for s in sel["link"].split(", "):
                el = item.select_one(s.strip())
                if el and el.get("href"):
                    href = el["href"]
                    link = href if href.startswith("http") else urljoin(source["base"], href)
                    break
            if not link: link = source["base"]
            photos = []
            for s in sel["image"].split(", "):
                for img in item.select(s.strip())[:5]:
                    src = img.get("src") or img.get("data-src") or ""
                    if src and "placeholder" not in src:
                        if not src.startswith("http"): src = urljoin(source["base"], src)
                        photos.append(src)
                if photos: break
            desc = ""
            for s in sel["description"].split(", "):
                el = item.select_one(s.strip())
                if el and len(el.get_text(strip=True)) > 20: desc = el.get_text(strip=True)[:500]; break
            if not desc: desc = title
            full = f"{title} {loc_txt} {desc} {link}"
            zone = detect_zone(f"{loc_txt} {title}")
            transaction = detect_transaction(full)
            type_bien = detect_type(full)
            prix_fcfa, prix_display = extract_price(prix_txt)
            zones_ok = not config["zones"] or any(z.lower() in zone.lower() for z in config["zones"])
            if not zones_ok: continue
            if transaction == "Location" and prix_fcfa > 0 and prix_fcfa < config["min_loyer"]: continue
            if transaction == "Vente" and prix_fcfa > 0 and prix_fcfa < config["min_vente"]: continue
            surface_m = re.search(r"(\d+)\s*m[²2]", full, re.IGNORECASE)
            surface = surface_m.group(1) + "m²" if surface_m else ""
            pieces_m = re.search(r"(\d+)\s*(pièces?|chambres?)", full, re.IGNORECASE)
            pieces = pieces_m.group(1) if pieces_m else ""
            phone_m = re.search(r"(\+?225\s?[\d\s]{8,14}|07\s?\d{2}\s?\d{2}\s?\d{2})", full)
            contact = phone_m.group(0).strip() if phone_m else ""
            if not title or len(title) < 5: continue
            annonces.append({"id":make_id(link,title),"source":source["name"],"source_url":source["base"],"transaction":transaction,"type_bien":type_bien,"zone":zone,"quartier":loc_txt[:100] if loc_txt else zone,"prix":prix_display or "Prix NC","prix_fcfa":prix_fcfa,"surface":surface,"pieces":pieces,"contact":contact,"agence":source["name"],"description":desc,"url":link,"photos":json.dumps(photos[:6]),"publie_at":datetime.now().isoformat(),"scraped_at":datetime.now().isoformat(),"is_new":1})
        except: continue
    return annonces

def save_annonces(db_path, annonces):
    if not annonces: return 0
    conn = sqlite3.connect(db_path)
    saved = 0
    for a in annonces:
        try:
            conn.execute("INSERT OR REPLACE INTO annonces (id,source,source_url,transaction,type_bien,zone,quartier,prix,prix_fcfa,surface,pieces,contact,agence,description,url,photos,publie_at,scraped_at,is_new) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(a["id"],a["source"],a["source_url"],a["transaction"],a["type_bien"],a["zone"],a["quartier"],a["prix"],a["prix_fcfa"],a["surface"],a["pieces"],a["contact"],a["agence"],a["description"],a["url"],a["photos"],a["publie_at"],a["scraped_at"],a["is_new"]))
            saved += 1
        except: pass
    conn.commit(); conn.close()
    return saved

def run_scrape(db_path, config):
    global _status
    _status = {"running":True,"progress":0,"current":"","total":0,"done":0,"log":_status.get("log",[])}
    sources_to_run = SOURCES
    if config.get("sources"):
        sources_to_run = [s for s in SOURCES if s["id"] in config["sources"]]
    total_src = len(sources_to_run)
    total_annonces = 0
    _log(f"Démarrage — {total_src} sources | zones: {config['zones'][:3]}", "info")
    conn = sqlite3.connect(db_path)
    conn.execute("UPDATE annonces SET is_new=0")
    conn.commit(); conn.close()
    for i, source in enumerate(sources_to_run):
        _status["current"] = source["name"]
        _status["progress"] = int((i / total_src) * 100)
        _log(f"[{i+1}/{total_src}] {source['name']}", "info")
        src_count = 0
        for url in source["urls"]:
            html = fetch_page(url)
            if not html: html = fetch_page_playwright(url)
            annonces = parse_annonces(html, source, config)
            saved = save_annonces(db_path, annonces)
            src_count += saved
            _log(f"  {saved} annonces sauvegardées", "ok")
            time.sleep(1.5)
        total_annonces += src_count
        _status["done"] = i + 1
    _status["running"] = False
    _status["progress"] = 100
    _status["current"] = ""
    _log(f"Terminé — {total_annonces} annonces collectées", "ok")
    conn = sqlite3.connect(db_path)
    conn.execute("INSERT INTO scrape_jobs (started_at,finished_at,status,total,config) VALUES (?,?,?,?,?)",(datetime.now().isoformat(),datetime.now().isoformat(),"done",total_annonces,json.dumps(config)))
    conn.commit(); conn.close()
