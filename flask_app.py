import hashlib
import os
import re
import secrets
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from flask import (
    Flask, abort, flash, redirect, render_template_string,
    request, send_from_directory, session, url_for
)
from werkzeug.utils import secure_filename


# Paths and basic settings
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
UPLOAD_DIR = STATIC_DIR / "uploads"
DATABASE_PATH = BASE_DIR / "harvest.db"
LOGO_FILENAME = "harvest_logo.jpg"

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png"}
MAX_IMAGE_SIZE = 8 * 1024 * 1024  # 8 MB per image

STATIC_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get("HARVEST_SECRET") or os.environ.get("HASAD_SECRET"),
    MAX_CONTENT_LENGTH=MAX_IMAGE_SIZE + 1024 * 1024,
)

# A fixed secret should be set in PythonAnywhere's WSGI file.
# This fallback is useful for local testing, but changes after a restart.
if not app.config["SECRET_KEY"]:
    app.config["SECRET_KEY"] = secrets.token_hex(32)

CATEGORIES = [
    "محاصيل",
    "خضراوات وفاكهة",
    "بذور وشتلات",
    "أسمدة ومغذيات",
    "مستلزمات وقاية النبات",
    "معدات وآلات",
    "أعلاف ومستلزمات حيوانية",
    "خدمات زراعية",
    "أخرى",
]
CURRENCIES = {
    "EGP": "جنيه مصري",
    "USD": "دولار أمريكي",
    "EUR": "يورو",
}
TRANSLATIONS = {
    "ar": {
        "name": "هارڤيست | HARVEST",
        "tagline": "من الأرض .. نحصد الاقتصاد",
        "market": "السوق الزراعي",
        "sell": "أضف إعلانًا",
        "plant": "صحة النبات",
        "map": "الخريطة",
        "search": "ابحث عن منتج أو قسم أو منطقة",
        "all": "كل الأقسام",
        "search_btn": "بحث",
        "latest": "أحدث الإعلانات",
        "empty": "لا توجد إعلانات حتى الآن. كن أول من يضيف إعلانًا.",
        "details": "التفاصيل",
        "category": "القسم",
        "description": "الوصف",
        "price": "السعر",
        "place": "المنطقة / المحافظة",
        "phone": "رقم التواصل",
        "image": "صورة المنتج",
        "publish": "نشر الإعلان",
        "back": "العودة للسوق",
        "not_found": "الإعلان غير موجود.",
        "required": "من فضلك أكمل جميع البيانات المطلوبة.",
        "bad_image": "اختر صورة بصيغة JPG أو PNG.",
        "bad_price": "اكتب سعرًا صحيحًا أو اترك السعر فارغًا.",
        "saved": "تم نشر الإعلان بنجاح.",
        "plant_note": "يمكنك استخدام هذه الصفحة لاحقًا لإضافة أداة فحص صحة النبات.",
        "map_note": "يمكن إضافة خريطة تفاعلية للمناطق الزراعية في تحديث لاحق.",
        "contact": "تواصل مع المعلن",
        "no_price": "السعر غير محدد",
    },
    "en": {
        "name": "HARVEST | هارڤيست",
        "tagline": "From Earth, Economy Grows",
        "market": "Agricultural marketplace",
        "sell": "Post a listing",
        "plant": "Plant health",
        "map": "Map",
        "search": "Search products, categories or locations",
        "all": "All categories",
        "search_btn": "Search",
        "latest": "Latest listings",
        "empty": "No listings yet. Be the first to post one.",
        "details": "Details",
        "category": "Category",
        "description": "Description",
        "price": "Price",
        "place": "Area / governorate",
        "phone": "Contact number",
        "image": "Product image",
        "publish": "Publish listing",
        "back": "Back to marketplace",
        "not_found": "Listing not found.",
        "required": "Please complete all required fields.",
        "bad_image": "Choose a JPG or PNG image.",
        "bad_price": "Enter a valid price or leave it blank.",
        "saved": "Your listing has been published.",
        "plant_note": "A plant-health checking tool can be added to this page later.",
        "map_note": "An interactive map of agricultural areas can be added in a future update.",
        "contact": "Contact seller",
        "no_price": "Price not specified",
    },
}

# The page is kept in this file so it can be uploaded as a single Flask file.
PAGE = r"""
<!doctype html>
<html lang="{{ lang }}" dir="{{ 'rtl' if lang == 'ar' else 'ltr' }}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{ page_title }} | HARVEST</title>
  <style>
    :root { --green:#286447; --deep:#173f2d; --cream:#f5f7f1; --gold:#d7ad52; }
    * { box-sizing:border-box; }
    body { margin:0; background:var(--cream); color:#24342b;
           font-family:Tahoma,Arial,sans-serif; line-height:1.7; }
    a { color:inherit; text-decoration:none; }
    .top { background:var(--deep); color:white; padding:12px 5%; }
    .nav { max-width:1100px; margin:auto; display:flex; align-items:center;
           justify-content:space-between; gap:16px; flex-wrap:wrap; }
    .brand { display:flex; align-items:center; gap:12px; font-weight:bold; font-size:1.2rem; }
    .logo { width:52px; height:52px; object-fit:contain; border-radius:10px; background:white; }
    .logo-fallback { width:52px; height:52px; display:grid; place-items:center;
                     border-radius:10px; background:var(--gold); color:var(--deep); }
    .links { display:flex; gap:16px; align-items:center; flex-wrap:wrap; }
    .links a:hover { color:var(--gold); }
    .container { max-width:1100px; margin:28px auto; padding:0 18px; }
    .hero { background:linear-gradient(125deg,#173f2d,#347b52); color:white;
            padding:30px; border-radius:18px; margin-bottom:24px; }
    .hero h1 { margin:0 0 6px; font-size:clamp(1.5rem,4vw,2.2rem); }
    .muted { color:#68776d; }
    .hero .muted { color:#e2eee5; }
    .panel { background:white; padding:22px; border-radius:15px;
             box-shadow:0 5px 22px #163d2b0d; margin-bottom:22px; }
    .search { display:grid; grid-template-columns:2fr 1fr auto; gap:10px; }
    input,select,textarea,button { font:inherit; }
    input,select,textarea { width:100%; border:1px solid #d5ded7; border-radius:9px;
                            padding:11px 12px; background:white; }
    textarea { min-height:120px; resize:vertical; }
    label { display:block; margin:12px 0 5px; font-weight:bold; }
    .btn { display:inline-block; border:0; border-radius:9px; padding:10px 17px;
           background:var(--green); color:white; cursor:pointer; text-align:center; }
    .btn:hover { background:var(--deep); }
    .btn.secondary { background:#e9f0e9; color:var(--deep); }
    .grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:18px; }
    .card { overflow:hidden; padding:0; }
    .product-image { width:100%; height:190px; object-fit:cover; display:block; background:#edf1eb; }
    .card-body { padding:16px; }
    .card h3 { margin:0 0 5px; }
    .tag { display:inline-block; border-radius:30px; padding:3px 10px;
           background:#edf4ed; color:var(--green); font-size:.85rem; }
    .price { color:var(--green); font-weight:bold; margin:8px 0; }
    .flash { padding:12px 15px; background:#fff3cd; border-radius:9px; margin-bottom:12px; }
    .form-grid { display:grid; grid-template-columns:1fr 1fr; gap:0 16px; }
    .full { grid-column:1/-1; }
    .detail-image { width:100%; max-height:430px; object-fit:contain; background:#f0f3ef; border-radius:12px; }
    footer { text-align:center; color:#718075; padding:25px; }
    @media(max-width:650px) {
      .search,.form-grid { grid-template-columns:1fr; }
      .full { grid-column:auto; }
      .hero { padding:22px; }
    }
  </style>
</head>
<body>
<header class="top">
  <div class="nav">
    <a class="brand" href="{{ url_for('home', lang=lang) }}">
      {% if logo_exists %}
        <img class="logo" src="{{ url_for('static', filename='harvest_logo.jpg') }}" alt="HARVEST logo">
      {% else %}
        <span class="logo-fallback">H</span>
      {% endif %}
      <span>{{ t.name }}<small style="display:block;font-size:.75rem;font-weight:normal">{{ t.tagline }}</small></span>
    </a>
    <nav class="links">
      <a href="{{ url_for('home', lang=lang) }}">{{ t.market }}</a>
      <a href="{{ url_for('add', lang=lang) }}">{{ t.sell }}</a>
      <a href="{{ url_for('plant_health', lang=lang) }}">{{ t.plant }}</a>
      <a href="{{ url_for('map_view', lang=lang) }}">{{ t.map }}</a>
      <a href="{{ request.path }}?lang={{ 'en' if lang == 'ar' else 'ar' }}">{{ 'English' if lang == 'ar' else 'العربية' }}</a>
    </nav>
  </div>
</header>

<main class="container">
  {% with messages = get_flashed_messages() %}
    {% for message in messages %}<div class="flash">{{ message }}</div>{% endfor %}
  {% endwith %}

  {% if page == 'home' %}
    <section class="hero">
      <h1>{{ t.market }}</h1>
      <div class="muted">{{ t.tagline }}</div>
      <p><a class="btn" href="{{ url_for('add', lang=lang) }}">{{ t.sell }}</a></p>
    </section>
    <section class="panel">
      <form class="search" method="get" action="{{ url_for('home') }}">
        <input type="hidden" name="lang" value="{{ lang }}">
        <input name="q" value="{{ query }}" placeholder="{{ t.search }}">
        <select name="category">
          <option value="">{{ t.all }}</option>
          {% for category in categories %}
            <option value="{{ category }}" {% if selected_category == category %}selected{% endif %}>{{ category }}</option>
          {% endfor %}
        </select>
        <button class="btn" type="submit">{{ t.search_btn }}</button>
      </form>
    </section>
    <h2>{{ t.latest }} <span class="muted">({{ total }})</span></h2>
    {% if products %}
      <section class="grid">
      {% for product in products %}
        <article class="panel card">
          <img class="product-image" src="{{ url_for('uploaded_file', filename=product['image_name']) }}" alt="{{ product['title'] }}">
          <div class="card-body">
            <span class="tag">{{ product['category'] }}</span>
            <h3>{{ product['title'] }}</h3>
            <div class="muted">{{ product['place'] }}</div>
            <div class="price">
              {% if product['price'] is not none %}{{ '%.2f'|format(product['price']) }} {{ currencies.get(product['currency'], product['currency']) }}
              {% else %}{{ t.no_price }}{% endif %}
            </div>
            <a class="btn secondary" href="{{ url_for('product_detail', product_id=product['id'], lang=lang) }}">{{ t.details }}</a>
          </div>
        </article>
      {% endfor %}
      </section>
    {% else %}
      <section class="panel">{{ t.empty }}</section>
    {% endif %}

  {% elif page == 'add' %}
    <section class="panel">
      <h1>{{ t.sell }}</h1>
      <form method="post" enctype="multipart/form-data">
        <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
        <div class="form-grid">
          <div>
            <label for="title">{{ 'اسم المنتج' if lang == 'ar' else 'Product name' }} *</label>
            <input id="title" name="title" maxlength="120" required>
          </div>
          <div>
            <label for="category">{{ t.category }} *</label>
            <select id="category" name="category" required>
              {% for category in categories %}<option value="{{ category }}">{{ category }}</option>{% endfor %}
            </select>
          </div>
          <div class="full">
            <label for="description">{{ t.description }} *</label>
            <textarea id="description" name="description" maxlength="3000" required></textarea>
          </div>
          <div>
            <label for="price">{{ t.price }}</label>
            <input id="price" name="price" type="number" min="0" step="0.01">
          </div>
          <div>
            <label for="currency">{{ 'العملة' if lang == 'ar' else 'Currency' }}</label>
            <select id="currency" name="currency">
              {% for code, label in currencies.items() %}<option value="{{ code }}">{{ label }}</option>{% endfor %}
            </select>
          </div>
          <div>
            <label for="place">{{ t.place }} *</label>
            <input id="place" name="place" maxlength="120" required>
          </div>
          <div>
            <label for="phone">{{ t.phone }} *</label>
            <input id="phone" name="phone" type="tel" maxlength="30" required>
          </div>
          <div class="full">
            <label for="file">{{ t.image }} *</label>
            <input id="file" name="file" type="file" accept=".jpg,.jpeg,.png,image/jpeg,image/png" required>
            <small class="muted">JPG / PNG — maximum 8 MB</small>
          </div>
        </div>
        <p><button class="btn" type="submit">{{ t.publish }}</button></p>
      </form>
    </section>

  {% elif page == 'detail' %}
    <section class="panel">
      <img class="detail-image" src="{{ url_for('uploaded_file', filename=product['image_name']) }}" alt="{{ product['title'] }}">
      <h1>{{ product['title'] }}</h1>
      <span class="tag">{{ product['category'] }}</span>
      <p class="price">
        {% if product['price'] is not none %}{{ '%.2f'|format(product['price']) }} {{ currencies.get(product['currency'], product['currency']) }}
        {% else %}{{ t.no_price }}{% endif %}
      </p>
      <h3>{{ t.description }}</h3>
      <p style="white-space:pre-wrap">{{ product['description'] }}</p>
      <p><strong>{{ t.place }}:</strong> {{ product['place'] }}</p>
      <p><strong>{{ t.phone }}:</strong> {{ product['phone'] }}</p>
      <p><a class="btn" href="https://wa.me/{{ product['phone']|replace('+','')|replace(' ','')|replace('-','') }}" target="_blank" rel="noopener noreferrer">{{ t.contact }}</a></p>
      <a class="btn secondary" href="{{ url_for('home', lang=lang) }}">{{ t.back }}</a>
    </section>

  {% elif page == 'plant' %}
    <section class="panel">
      <h1>{{ t.plant }}</h1>
      <p>{{ t.plant_note }}</p>
      <p class="muted">{{ 'هذه الصفحة توضيحية حاليًا ولا تشخّص أمراض النباتات.' if lang == 'ar' else 'This page is informational and does not currently diagnose plant diseases.' }}</p>
    </section>

  {% elif page == 'map' %}
    <section class="panel">
      <h1>{{ t.map }}</h1>
      <p>{{ t.map_note }}</p>
    </section>
  {% endif %}
</main>
<footer>HARVEST · {{ t.tagline }}</footer>
</body>
</html>
"""


@contextmanager
def database():
    connection = sqlite3.connect(DATABASE_PATH, timeout=15)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def init_db():
    with database() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                category TEXT NOT NULL,
                description TEXT NOT NULL,
                price REAL,
                currency TEXT NOT NULL DEFAULT 'EGP',
                place TEXT NOT NULL,
                phone TEXT NOT NULL,
                image_name TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )


# Create the table when the application starts on PythonAnywhere.
init_db()


def get_lang():
    lang = request.args.get("lang", "ar")
    return lang if lang in ("ar", "en") else "ar"


def csrf_token():
    token = session.get("_csrf_token")
    if token is None:
        token = secrets.token_urlsafe(32)
        session["_csrf_token"] = token
    return token


def valid_csrf():
    sent_token = request.form.get("csrf_token", "")
    saved_token = session.get("_csrf_token", "")
    return bool(sent_token and saved_token and secrets.compare_digest(sent_token, saved_token))


def allowed_image(file_storage):
    """Check both the filename extension and the file's actual image signature."""
    filename = secure_filename(file_storage.filename or "")
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if extension not in ALLOWED_EXTENSIONS:
        return False

    # Read a few bytes to verify that the uploaded file looks like a JPG or PNG.
    header = file_storage.stream.read(8)
    file_storage.stream.seek(0)
    is_jpeg = header.startswith(b"\xff\xd8\xff")
    is_png = header.startswith(b"\x89PNG\r\n\x1a\n")
    return is_jpeg or is_png


def render_page(page, page_title, **context):
    lang = context.get("lang", get_lang())
    common = {
        "page": page,
        "page_title": page_title,
        "lang": lang,
        "t": TRANSLATIONS[lang],
        "logo_exists": (STATIC_DIR / LOGO_FILENAME).is_file(),
        "categories": CATEGORIES,
        "currencies": CURRENCIES,
        "csrf_token": csrf_token(),
    }
    common.update(context)
    return render_template_string(PAGE, **common)


@app.route("/")
def home():
    lang = get_lang()
    query = request.args.get("q", "").strip()[:120]
    selected_category = request.args.get("category", "").strip()
    sql = "SELECT * FROM products WHERE 1=1"
    values = []

    if query:
        sql += " AND (title LIKE ? OR description LIKE ? OR place LIKE ? OR category LIKE ?)"
        pattern = f"%{query}%"
        values.extend([pattern, pattern, pattern, pattern])

    if selected_category in CATEGORIES:
        sql += " AND category = ?"
        values.append(selected_category)
    else:
        selected_category = ""

    sql += " ORDER BY id DESC"
    with database() as connection:
        products = connection.execute(sql, values).fetchall()

    return render_page(
        "home",
        TRANSLATIONS[lang]["market"],
        lang=lang,
        products=products,
        total=len(products),
        query=query,
        selected_category=selected_category,
    )


@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    # Only serve a simple filename from the upload directory.
    if Path(filename).name != filename or filename.startswith("."):
        abort(404)
    return send_from_directory(UPLOAD_DIR, filename)


@app.route("/add", methods=["GET", "POST"])
def add():
    lang = get_lang()
    t = TRANSLATIONS[lang]

    if request.method == "POST":
        if not valid_csrf():
            abort(400, description="Invalid form token. Reload the page and try again.")

        title = request.form.get("title", "").strip()
        category = request.form.get("category", "").strip()
        description = request.form.get("description", "").strip()
        price_text = request.form.get("price", "").strip()
        currency = request.form.get("currency", "EGP").strip()
        place = request.form.get("place", "").strip()
        phone = request.form.get("phone", "").strip()
        image = request.files.get("file")

        if (
            not title or len(title) > 120
            or category not in CATEGORIES
            or not description or len(description) > 3000
            or not place or len(place) > 120
            or not phone or len(phone) > 30
            or currency not in CURRENCIES
            or image is None or not image.filename
        ):
            flash(t["required"])
            return redirect(url_for("add", lang=lang))

        price = None
        if price_text:
            try:
                price = float(price_text)
                if price < 0 or price != price or price == float("inf"):
                    raise ValueError
            except ValueError:
                flash(t["bad_price"])
                return redirect(url_for("add", lang=lang))

        if not allowed_image(image):
            flash(t["bad_image"])
            return redirect(url_for("add", lang=lang))

        original_name = secure_filename(image.filename)
        extension = original_name.rsplit(".", 1)[-1].lower()
        # A generated name avoids overwriting files with the same original name.
        image_name = f"{uuid.uuid4().hex}.{extension}"
        image_path = UPLOAD_DIR / image_name

        try:
            image.save(image_path)
            image_hash = hashlib.sha256(image_path.read_bytes()).hexdigest()
            with database() as connection:
                # Support databases created by earlier versions that included
                # an image_hash column marked NOT NULL. Keep the existing DB.
                columns = {
                    row["name"]
                    for row in connection.execute("PRAGMA table_info(products)").fetchall()
                }
                insert_columns = [
                    "title", "category", "description", "price", "currency",
                    "place", "phone", "image_name", "created_at",
                ]
                insert_values = [
                    title, category, description, price, currency, place, phone,
                    image_name, datetime.now(timezone.utc).isoformat(),
                ]
                if "image_hash" in columns:
                    insert_columns.append("image_hash")
                    insert_values.append(image_hash)

                placeholders = ", ".join("?" for _ in insert_columns)
                column_sql = ", ".join(insert_columns)
                connection.execute(
                    f"INSERT INTO products ({column_sql}) VALUES ({placeholders})",
                    insert_values,
                )
        except Exception:
            # Avoid leaving an unreferenced file if the database write fails.
            image_path.unlink(missing_ok=True)
            app.logger.exception("Could not save a new listing")
            abort(500)

        flash(t["saved"])
        return redirect(url_for("home", lang=lang))

    return render_page("add", t["sell"], lang=lang)


@app.route("/product/<int:product_id>")
def product_detail(product_id):
    lang = get_lang()
    with database() as connection:
        product = connection.execute(
            "SELECT * FROM products WHERE id = ?", (product_id,)
        ).fetchone()

    if product is None:
        abort(404)

    return render_page(
        "detail", product["title"], lang=lang, product=product
    )


@app.route("/plant")
def plant_health():
    lang = get_lang()
    return render_page("plant", TRANSLATIONS[lang]["plant"], lang=lang)


@app.route("/map")
def map_view():
    lang = get_lang()
    return render_page("map", TRANSLATIONS[lang]["map"], lang=lang)


@app.errorhandler(413)
def too_large(_error):
    lang = get_lang()
    message = (
        "حجم الصورة أكبر من الحد المسموح (8 ميجابايت)."
        if lang == "ar"
        else "Image is larger than the allowed limit (8 MB)."
    )
    return (
        "<!doctype html><html lang='" + lang + "' dir='" +
        ("rtl" if lang == "ar" else "ltr") +
        "'><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'>"
        "<title>HARVEST</title><body style='font-family:Arial,Tahoma,sans-serif;padding:24px'>"
        "<h2>HARVEST</h2><p>" + message + "</p><a href='/add?lang=" + lang + "'>" +
        ("العودة لإضافة الإعلان" if lang == "ar" else "Back to add listing") +
        "</a></body></html>",
        413,
    )


if __name__ == "__main__":
    # Debug mode is intentionally off for safer deployment.
    app.run(debug=False)