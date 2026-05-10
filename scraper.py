import requests, sqlite3, json, hashlib, re, time, os
from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import urljoin
import urllib3
urllib3.disable_warnings()

_status = {"running": False, "progress": 0, "current": "", "total": 0, "done": 0, "log": []}

def get_status():
    return dict(_status)

def _log(msg, level="info"):
    t = datetime.now().strftime("%H:%M:%S")
    _status["log"] = (_status["log"] + [{"t": t, "msg": msg, "level": level}])[-80:]
    print(f"[{t}] {msg}")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}

# Sites accessibles depuis serveurs internationaux
SOURCES = [
    {
        "id": "coinafrique",
        "name": "CoinAfrique CI",
        "base": "https://ci.coinafrique.com",
        "urls": [
            "https://ci.coinafrique.com/annonces/immobilier-appartements-cote-d-ivoire",
            "https://ci.coinafrique.com/annonces/immobilier-villas-cote-d-ivoire",
            "https://ci.coinafrique.com/annonces/immobilier-terrains-cote-d-ivoire",
        ],
        "selectors": {
            "items": ".card, .ad-card, [class*='card'], [class*='listing']",
            "title": "h2, h3, p, .title, [class*='title']",
            "price": "[class*='price'], .price, strong, b",
            "location": "[class*='location'], [class*='address'], [class*='city'], small",
            "link": "a",
            "image": "img",
            "description": "p, [class*='desc']",
        }
    },
    {
        "id": "jumia",
        "name": "Jumia House CI",
        "base": "https://www.jumia.ci",
        "urls": [
            "https://www.jumia.ci/immobilier/",
        ],
        "selectors": {
            "items": "article, .prd, [class*='product'], [class*='listing']",
            "title": "h3, h2, [class*='name'], [class*='title']",
            "price": "[class*='price'], .price, strong",
            "location": "[class*='location'], small, [class*='city']",
            "link": "a",
            "image": "img",
            "description": "p",
        }
    },
    {
        "id": "tontonimmo",
        "name": "Tonton Immo",
        "base": "https://www.tontonimmo.com",
        "urls": [
            "https://www.tontonimmo.com/",
            "https://www.tontonimmo.com/locations",
            "https://www.tontonimmo.com/ventes",
        ],
        "selectors": {
            "items": "[class*='property'], [class*='bien'], [class*='listing'], article, .card",
            "title": "h2, h3, [class*='title'], [class*='name']",
            "price": "[class*='price'], [class*='prix'], strong, b",
            "location": "[class*='location'], [class*='address'], [class*='ville'], small",
            "link": "a",
            "image": "img",
            "description": "p",
        }
    },
    {
        "id": "luxury",
        "name": "Luxury Home Abidjan",
        "base": "https://luxuryhomeabidjan.com",
        "urls": [
            "https://luxuryhomeabidjan.com/",
            "https://luxuryhomeabidjan.com/location/",
            "https://luxuryhomeabidjan.com/vente/",
        ],
        "selectors": {
            "items": "[class*='property'], [class*='listing'], article, .card, [class*='bien']",
            "title": "h2, h3, [class*='title']",
            "price": "[class*='price'], [class*='prix'], strong",
            "location": "[class*='location'], [class*='address'], small",
            "link": "a",
            "image": "img",
            "description": "p",
        }
    },
    {
        "id": "yapgi",
        "name": "Yapgi Immobilier",
        "base": "https://yapgi-immobilier.com",
        "urls": [
            "https://yapgi-immobilier.com/",
            "https://yapgi-immobilier.com/location",
            "https://yapgi-immobilier.com/vente",
        ],
        "selectors": {
            "items": "[class*='property'], [class*='listing'], article, .card",
            "title": "h2, h3, [class*='title']",
            "price": "[class*='price'], strong",
            "location": "[class*='location'], small",
            "link": "a",
            "image": "img",
            "description": "p",
        }
    },
    {
        "id": "kle",
        "name": "KLE Immobilier",
        "base": "https://kleimmobilier.com",
        "urls": [
            "https://kleimmobilier.com/",
            "https://kleimmobilier.com/location",
            "https://kleimmobilier.com/vente",
        ],
        "selectors": {
            "items": "[class*='property'], [class*='listing'], article, .card, li",
            "title": "h2, h3, [class*='title'], a",
            "price": "[class*='price'], strong, b",
            "location": "[class*='location'], [class*='city'], small, span",
            "link": "a",
            "image": "img",
            "description": "p, span",
        }
    },
    {
        "id": "mdimmo",
        "name": "MD Immo CI",
        "base": "https://mdimmo-ci.com",
        "urls": [
            "https://mdimmo-ci.com/",
            "https://mdimmo-ci.com/location",
            "https://mdimmo-ci.com/vente",
        ],
        "selectors": {
            "items": "[class*='property'], [class*='listing'], article, .card, [class*='bien']",
            "title": "h2, h3, [class*='title']",
            "price": "[class*='price'], [class*='prix'], strong",
            "location": "[class*='location'], [class*='address'], small",
            "link": "a",
            "image": "img",
            "description": "p",
        }
    },
    {
        "id": "kalimba",
        "name": "Kalimba Immobilier",
        "base": "https://kalimbaimmobilier.com",
        "urls": [
            "https://kalimbaimmobilier.com/",
        ],
        "selectors": {
            "items": "[class*='property'], [class*='listing'], article, .card",
            "title": "h2, h3, [class*='title']",
            "price": "[class*='price'], strong",
            "location": "[class*='location'], small",
            "link": "a",
            "image": "img",
            "description": "p",
        }
    },
]

def extract_price(text):
    if not text: return 0, ""
    clean = re.sub(r"[^\d]", "", text)
    val = int(clean) if clean else 0
    if "million" in text.lower(): val *= 1000000
    elif val > 0 and val < 5000 and "000" not in text: val *= 1000
    return val, text.strip()

def detect_tx(text, url=""):
    t = (text + " " + url).lower()
    if any(w in t for w in ["vente","a vendre","achat","for-sale","sale","cession"]): return "Vente"
    if any(w in t for w in ["location","louer","a louer","loyer","for-rent","rent","bail"]): return "Location"
    return "Vente"

def detect_type(text):
    t = text.lower()
    for typ, kws in [("Villa",["villa"]),("Appartement",["appartement","appart","apartment"]),("Studio",["studio"]),("Duplex",["duplex"]),("Terrain",["terrain","parcelle","land","plot"]),("Immeuble",["immeuble","building"]),("Bureau",["bureau","office"]),("Local commercial",["local commercial","boutique","commercial"]),("Magasin",["magasin"]),("Entrepot",["entrepot","hangar","warehouse"]),("Chambre",["chambre","room"]),("Maison",["maison","house"])]:
        if any(kw in t for kw in kws): return typ
    return "Appartement"

def detect_zone(text):
    t = text.lower()
    for zone, kws in [("Cocody",["cocody"]),("Riviera Golf",["riviera golf","golf"]),("Riviera",["riviera"]),("2 Plateaux",["2 plateaux","deux plateaux"]),("Angre",["angre"]),("Marcory",["marcory"]),("Zone 4",["zone 4","zone4"]),("Bietry",["bietry"]),("Plateau",["plateau"]),("Treichville",["treichville"]),("Yopougon",["yopougon"]),("Koumassi",["koumassi"]),("Adjame",["adjame"]),("Abobo",["abobo"]),("Bingerville",["bingerville"]),("Bassam",["bassam"]),("Djibi",["djibi"]),("Palmeraie",["palmeraie"])]:
        if any(kw in t for kw in kws): return zone
    return "Abidjan"

def make_id(url, title):
    return hashlib.md5(f"{url}{title}".encode()).hexdigest()[:16]

def fetch_page(url, timeout=25):
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True, verify=False)
        r.raise_for_status()
        r.encoding = r.apparent_encoding or "utf-8"
        _log(f"  OK {url} ({len(r.text)} chars)", "ok")
        return r.text
    except Exception as e:
        _log(f"Erreur fetch {url}: {e}", "err")
        return None

def parse_annonces(html, source, config):
    if not html: return []
    soup = BeautifulSoup(html, "html.parser")
    sel = source["selectors"]
    items = []
    for selector in sel["items"].split(", "):
        found = soup.select(selector.strip())
        if len(found) > 1:
            items = found
            break
    if not items:
        items = soup.select("article, .card, li, div[class]")
        items = [i for i in items if len(i.get_text(strip=True)) > 30][:30]
    _log(f"  {len(items)} elements sur {source['name']}", "info")
    annonces = []
    for item in items[:20]:
        try:
            title = ""
            for s in sel["title"].split(", "):
                el = item.select_one(s.strip())
                if el and len(el.get_text(strip=True)) > 4:
                    title = el.get_text(strip=True)[:200]; break
            prix_txt = ""
            for s in sel["price"].split(", "):
                el = item.select_one(s.strip())
                if el and el.get_text(strip=True):
                    prix_txt = el.get_text(strip=True); break
            loc_txt = ""
            for s in sel["location"].split(", "):
                el = item.select_one(s.strip())
                if el and el.get_text(strip=True):
                    loc_txt = el.get_text(strip=True); break
            link = ""
            for s in sel["link"].split(", "):
                el = item.select_one(s.strip())
                if el and el.get("href"):
                    href = el["href"]
                    link = href if href.startswith("http") else urljoin(source["base"], href)
                    break
            if not link: link = source["base"]
            photos = []
            for img in item.select("img")[:4]:
                src = img.get("src") or img.get("data-src") or img.get("data-lazy") or ""
                if src and len(src) > 10 and not any(x in src for x in ["placeholder","logo","icon","flag"]):
                    if not src.startswith("http"): src = urljoin(source["base"], src)
                    photos.append(src)
            desc = ""
            for s in sel["description"].split(", "):
                el = item.select_one(s.strip())
                if el and len(el.get_text(strip=True)) > 15:
                    desc = el.get_text(strip=True)[:400]; break
            if not desc: desc = title
            full = f"{title} {loc_txt} {desc}"
            zone = detect_zone(f"{loc_txt} {title}")
            tx = detect_tx(full, link)
            type_bien = detect_type(full)
            prix_fcfa, prix_display = extract_price(prix_txt)
            zones_cfg = config.get("zones", [])
            if zones_cfg and not any(z.lower() in full.lower() for z in zones_cfg):
                continue
            if tx == "Location" and prix_fcfa > 0 and prix_fcfa < config.get("min_loyer", 0): continue
            if tx == "Vente" and prix_fcfa > 0 and prix_fcfa < config.get("min_vente", 0): continue
            if not title or len(title) < 5: continue
            surface_m = re.search(r"(\d+)\s*m[2²]", full, re.IGNORECASE)
            pieces_m = re.search(r"(\d+)\s*(pieces?|chambres?)", full, re.IGNORECASE)
            phone_m = re.search(r"(\+?225[\s\d]{8,15}|0[57]\d[\s\d]{6,10})", full)
            annonces.append({
                "id": make_id(link, title),
                "source": source["name"],
                "source_url": source["base"],
                "tx_type": tx,
                "type_bien": type_bien,
                "zone": zone,
                "quartier": loc_txt[:100] if loc_txt else zone,
                "prix": prix_display or "Prix NC",
                "prix_fcfa": prix_fcfa,
                "surface": surface_m.group(1) + "m2" if surface_m else "",
                "pieces": pieces_m.group(1) if pieces_m else "",
                "contact": phone_m.group(0).strip() if phone_m else "",
                "agence": source["name"],
                "description": desc,
                "url": link,
                "photos": json.dumps(photos[:4]),
                "publie_at": datetime.now().isoformat(),
                "scraped_at": datetime.now().isoformat(),
                "is_new": 1,
            })
        except: continue
    return annonces

def save_annonces(db_path, annonces):
    if not annonces: return 0
    conn = sqlite3.connect(db_path)
    saved = 0
    for a in annonces:
        try:
            conn.execute("INSERT OR REPLACE INTO annonces (id,source,source_url,tx_type,type_bien,zone,quartier,prix,prix_fcfa,surface,pieces,contact,agence,description,url,photos,publie_at,scraped_at,is_new) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (a["id"],a["source"],a["source_url"],a["tx_type"],a["type_bien"],a["zone"],a["quartier"],a["prix"],a["prix_fcfa"],a["surface"],a["pieces"],a["contact"],a["agence"],a["description"],a["url"],a["photos"],a["publie_at"],a["scraped_at"],a["is_new"]))
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
    _log(f"Demarrage - {total_src} sources | zones: {config.get('zones',['Toutes'])[:3]}", "info")
    try:
        conn = sqlite3.connect(db_path)
        conn.execute("UPDATE annonces SET is_new=0")
        conn.commit(); conn.close()
    except: pass
    for i, source in enumerate(sources_to_run):
        _status["current"] = source["name"]
        _status["progress"] = int((i/total_src)*100)
        _log(f"[{i+1}/{total_src}] {source['name']}", "info")
        src_count = 0
        for url in source["urls"]:
            html = fetch_page(url)
            if html:
                annonces = parse_annonces(html, source, config)
                saved = save_annonces(db_path, annonces)
                src_count += saved
                _log(f"  {saved} annonces sauvegardees", "ok")
            time.sleep(1.5)
        total_annonces += src_count
        _status["done"] = i + 1
    _status["running"] = False
    _status["progress"] = 100
    _status["current"] = ""
    _log(f"Termine - {total_annonces} annonces collectees", "ok")
    try:
        conn = sqlite3.connect(db_path)
        conn.execute("INSERT INTO scrape_jobs (started_at,finished_at,status,total,config) VALUES (?,?,?,?,?)",
            (datetime.now().isoformat(),datetime.now().isoformat(),"done",total_annonces,json.dumps(config)))
        conn.commit(); conn.close()
    except: pass
