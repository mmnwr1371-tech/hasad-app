import hashlib
import hmac
import os
import re
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from functools import wraps

from flask import (
    Flask, abort, flash, redirect, render_template_string, request,
    send_from_directory, session, url_for
)
from werkzeug.utils import secure_filename

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
UPLOAD_DIR = STATIC_DIR / "uploads"
DATABASE_PATH = BASE_DIR / "harvest.db"
LOGO_FILENAME = "harvest_logo.jpg"
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png"}

app = Flask(__name__)

secret_key = os.environ.get("HARVEST_SECRET") or os.environ.get("HASAD_SECRET") or secrets.token_hex(32)
app.config.update(
    SECRET_KEY=secret_key,
    MAX_CONTENT_LENGTH=20 * 1024 * 1024,
)

STATIC_DIR.mkdir(exist_ok=True)
UPLOAD_DIR.mkdir(exist_ok=True)

TRANSLATIONS = {
    "ar": {"name": "هارڤيست | HARVEST", "tagline": "من الأرض .. نحصد الاقتصاد", "market": "السوق", "sell": "أضف إعلانًا", "plant": "صحة النبات", "map": "الخريطة", "admin": "الإدارة", "search": "ابحث عن منتج أو قسم أو منطقة"},
    "en": {"name": "HARVEST | هارڤيست", "tagline": "From Earth, Economy Grows", "market": "Marketplace", "sell": "Post a listing", "plant": "Plant health", "map": "Map", "admin": "Admin", "search": "Search products, categories or locations"},
}
CATEGORIES = ["محاصيل", "خضراوات وفاكهة", "بذور وشتلات", "أسمدة ومغذيات", "مستلزمات وقاية النبات", "معدات وآلات", "أعلاف ومستلزمات حيوانية", "خدمات زراعية", "أخرى"]
CURRENCIES = {"EGP": "جنيه مصري", "USD": "دولار أمريكي", "EUR": "يورو"}

# --- حط هنا الـ PAGE اللي انت باعته كامل بدون تغيير ---
# عشان الرسالة متبقاش طويلة، سيب الـ PAGE زي ما هو عندك
PAGE = r""" """  # <-- انسخ الـ PAGE اللي عندك هنا كامل

# ... باقي الكود اللي كان ناقص ...
@contextmanager
def database():
    conn = sqlite3.connect(DATABASE_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

def init_db():
    with database() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, category TEXT NOT NULL,
            description TEXT NOT NULL, price REAL, currency TEXT NOT NULL DEFAULT 'EGP',
            place TEXT NOT NULL, phone TEXT NOT NULL, image_name TEXT NOT NULL, created_at TEXT NOT NULL)""")

init_db()

def get_lang():
    return request.args.get("lang", "ar") if request.args.get("lang") in ("ar","en") else "ar"

@app.route("/")
def home():
    lang = get_lang()
    t = TRANSLATIONS[lang]
    logo_exists = (STATIC_DIR / LOGO_FILENAME).exists()
    with database() as conn:
        products = conn.execute("SELECT * FROM products ORDER BY id DESC").fetchall()
    return render_template_string(PAGE, page="home", lang=lang, t=t, logo_exists=logo_exists, products=products, total=len(products), categories=CATEGORIES, query="", selected_category="", selected_place="", page_title=t["market"])

@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_DIR, filename)

@app.route("/add", methods=["GET", "POST"])
def add():
    lang = get_lang()
    t = TRANSLATIONS[lang]
    logo_exists = (STATIC_DIR / LOGO_FILENAME).exists()
    if request.method == "POST":
        file = request.files.get("file")
        if file:
            fname = secure_filename(file.filename)
            file.save(UPLOAD_DIR / fname)
            with database() as conn:
                conn.execute("INSERT INTO products (title, category, description, price, currency, place, phone, image_name, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                             (request.form["title"], request.form["category"], request.form["description"], float(request.form["price"] or 0) or None, request.form["currency"], request.form["place"], request.form["phone"], fname, datetime.now(timezone.utc).isoformat()))
            return redirect(url_for("home", lang=lang))
    return render_template_string(PAGE, page="add", lang=lang, t=t, logo_exists=logo_exists, categories=CATEGORIES, currencies=CURRENCIES, csrf_token="dummy", page_title=t["sell"])

@app.route("/product/<int:product_id>")
def product_detail(product_id):
    lang = get_lang()
    t = TRANSLATIONS[lang]
    logo_exists = (STATIC_DIR / LOGO_FILENAME).exists()
    with database() as conn:
        p = conn.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
    if not p: abort(404)
    return render_template_string(PAGE, page="detail", lang=lang, t=t, logo_exists=logo_exists, product=p, whatsapp_text="", page_title=p["title"])

@app.route("/plant", methods=["GET","POST"])
def plant_health():
    lang = get_lang()
    t = TRANSLATIONS[lang]
    logo_exists = (STATIC_DIR / LOGO_FILENAME).exists()
    return render_template_string(PAGE, page="plant", lang=lang, t=t, logo_exists=logo_exists, uploaded=False, csrf_token="dummy", page_title=t["plant"])

@app.route("/map")
def map_view():
    lang = get_lang()
    t = TRANSLATIONS[lang]
    logo_exists = (STATIC_DIR / LOGO_FILENAME).exists()
    return render_template_string(PAGE, page="map", lang=lang, t=t, logo_exists=logo_exists, page_title=t["map"])

if __name__ == "__main__":
    app.run(debug=True)