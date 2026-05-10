from flask import Flask, jsonify, request, Response
from flask_cors import CORS
import sqlite3, os, json, threading, csv, io
from datetime import datetime, timedelta
from scraper import run_scrape, get_status

app = Flask(__name__)
CORS(app)
DB_PATH = os.environ.get("DB_PATH", "/tmp/immo.db")


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("CREATE TABLE IF NOT EXISTS annonces (id TEXT PRIMARY KEY, source TEXT, source_url TEXT, transaction TEXT, type_bien TEXT, zone TEXT, quartier TEXT, prix TEXT, prix_fcfa INTEGER DEFAULT 0, surface TEXT, pieces TEXT, contact TEXT, agence TEXT, description TEXT, url TEXT, photos TEXT DEFAULT '[]', publie_at TEXT, scraped_at TEXT, is_new INTEGER DEFAULT 0)")
    conn.execute("CREATE TABLE IF NOT EXISTS scrape_jobs (id INTEGER PRIMARY KEY AUTOINCREMENT, started_at TEXT, finished_at TEXT, status TEXT, total INTEGER DEFAULT 0, config TEXT)")
    conn.commit()
    conn.close()

init_db()

@app.route("/")
def home():
    return jsonify({"status": "ok", "service": "ImmoScraper CI API"})

@app.route("/api/annonces")
def get_annonces():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    q = "SELECT * FROM annonces WHERE 1=1"
    params = []
    days = int(request.args.get("days", 7))
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    q += " AND scraped_at >= ?"
    params.append(cutoff)
    tx = request.args.get("transaction")
    zone = request.args.get("zone")
    type_bien = request.args.get("type")
    search = request.args.get("search")
    min_prix = request.args.get("min_prix")
    sort = request.args.get("sort", "date")
    limit = min(int(request.args.get("limit", 200)), 500)
    if tx:
        q += " AND transaction = ?"
        params.append(tx)
    if zone:
        q += " AND zone LIKE ?"
        params.append(f"%{zone}%")
    if type_bien:
        q += " AND type_bien LIKE ?"
        params.append(f"%{type_bien}%")
    if min_prix:
        q += " AND prix_fcfa >= ?"
        params.append(int(min_prix))
    if search:
        s = f"%{search}%"
        q += " AND (zone LIKE ? OR quartier LIKE ? OR description LIKE ? OR type_bien LIKE ?)"
        params.extend([s, s, s, s])
    if sort == "price_asc":
        q += " ORDER BY prix_fcfa ASC"
    elif sort == "price_desc":
        q += " ORDER BY prix_fcfa DESC"
    elif sort == "surface":
        q += " ORDER BY CAST(surface AS INTEGER) DESC"
    else:
        q += " ORDER BY scraped_at DESC"
    q += f" LIMIT {limit}"
    rows = conn.execute(q, params).fetchall()
    conn.close()
    annonces = []
    for r in rows:
        a = dict(r)
        try:
            a["photos"] = json.loads(a.get("photos") or "[]")
        except:
            a["photos"] = []
        annonces.append(a)
    return jsonify({"annonces": annonces, "total": len(annonces)})

@app.route("/api/stats")
def get_stats():
    conn = sqlite3.connect(DB_PATH)
    total = conn.execute("SELECT COUNT(*) FROM annonces").fetchone()[0]
    ventes = conn.execute("SELECT COUNT(*) FROM annonces WHERE transaction='Vente'").fetchone()[0]
    locations = conn.execute("SELECT COUNT(*) FROM annonces WHERE transaction='Location'").fetchone()[0]
    new_24h = conn.execute("SELECT COUNT(*) FROM annonces WHERE is_new=1").fetchone()[0]
    sources = conn.execute("SELECT source, COUNT(*) as cnt FROM annonces GROUP BY source ORDER BY cnt DESC").fetchall()
    zones = conn.execute("SELECT zone, COUNT(*) as cnt FROM annonces GROUP BY zone ORDER BY cnt DESC LIMIT 15").fetchall()
    last_job = conn.execute("SELECT * FROM scrape_jobs ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    return jsonify({
        "total": total,
        "ventes": ventes,
        "locations": locations,
        "new_24h": new_24h,
        "sources": [{"name": r[0], "count": r[1]} for r in sources],
        "zones": [{"name": r[0], "count": r[1]} for r in zones],
        "last_job": dict(last_job) if last_job else None,
        "scrape_status": get_status(),
    })

@app.route("/api/scrape", methods=["POST"])
def launch_scrape():
    if get_status().get("running"):
        return jsonify({"error": "Scraping deja en cours"}), 409
    body = request.get_json(silent=True) or {}
    config = {
        "zones": body.get("zones", ["Cocody","Riviera","Riviera Golf","Marcory","Zone 4","Bietry","2 Plateaux","Angre"]),
        "types": body.get("types", []),
        "min_loyer": int(body.get("min_loyer", 1000000)),
        "min_vente": int(body.get("min_vente", 100000000)),
        "days": int(body.get("days", 7)),
        "sources": body.get("sources", []),
    }
    thread = threading.Thread(target=run_scrape, args=(DB_PATH, config), daemon=True)
    thread.start()
    return jsonify({"message": "Scraping lance", "config": config})

@app.route("/api/scrape/status")
def scrape_status():
    return jsonify(get_status())

@app.route("/api/annonces/export")
def export_csv():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM annonces ORDER BY scraped_at DESC").fetchall()
    conn.close()
    si = io.StringIO()
    si.write("\ufeff")
    writer = csv.writer(si, delimiter=";")
    writer.writerow(["ID","Source","Transaction","Type","Zone","Quartier","Prix","Prix FCFA","Surface","Pieces","Contact","Description","URL","Scrape"])
    for r in rows:
        writer.writerow([r["id"],r["source"],r["transaction"],r["type_bien"],r["zone"],r["quartier"],r["prix"],r["prix_fcfa"],r["surface"],r["pieces"],r["contact"],r["description"],r["url"],r["scraped_at"]])
    return Response(si.getvalue(), mimetype="text/csv", headers={"Content-Disposition":"attachment;filename=immo-ci.csv"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
