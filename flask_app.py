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
DATABASE_PATH = BASE_DIR / "hasad.db"
LOGO_RELATIVE_PATH = "1791466021118.jpg"
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png"}
MAX_TEXT_LENGTH = 500
CATEGORIES = [
    "محاصيل", "خضراوات وفاكهة", "بذور وشتلات", "أسمدة ومغذيات",
    "مستلزمات وقاية النبات", "معدات وآلات", "أعلاف ومستلزمات حيوانية",
    "خدمات زراعية", "أخرى"
]
CURRENCIES = {"EGP": "جنيه مصري", "USD": "دولار أمريكي", "EUR": "يورو"}

STATIC_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)
secret_key = os.environ.get("HASAD_SECRET")
if not secret_key or len(secret_key) < 32:
    secret_key = secrets.token_hex(32)
    app.logger.warning(
        "HASAD_SECRET is not configured. Set a stable secret of at least 32 characters before deployment."
    )

app.config.update(
    SECRET_KEY=secret_key,
    MAX_CONTENT_LENGTH=20 * 1024 * 1024,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("HASAD_HTTPS", "0") == "1",
    PERMANENT_SESSION_LIFETIME=3600,
)

TRANSLATIONS = {
    "ar": {
        "name": "حصاد | HASAD",
        "tagline": "منصة زراعية تربط الأسواق والمنتجين والمشترين",
        "market": "السوق",
        "sell": "أضف إعلانًا",
        "plant": "صحة النبات",
        "map": "الخريطة",
        "admin": "الإدارة",
        "search": "ابحث عن منتج أو قسم أو منطقة",
    },
    "en": {
        "name": "HASAD",
        "tagline": "An agricultural platform connecting markets, producers and buyers",
        "market": "Marketplace",
        "sell": "Post a listing",
        "plant": "Plant health",
        "map": "Map",
        "admin": "Admin",
        "search": "Search products, categories or locations",
    },
}

PAGE = r"""
<!doctype html>
<html lang="{{ lang }}" dir="{{ 'rtl' if lang == 'ar' else 'ltr' }}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#176b3a">
<title>{{ page_title }} · {{ t.name }}</title>
<style>
:root{--green:#176b3a;--green2:#0f4f2a;--mint:#edf6ef;--ink:#1e2b22;--muted:#66736a;--line:#e1e9e2;--gold:#e6b83f}
*{box-sizing:border-box}
body{margin:0;background:#f6f8f6;color:var(--ink);font-family:Tahoma,Arial,sans-serif;line-height:1.6}
a{color:inherit}
header{background:linear-gradient(120deg,var(--green2),var(--green));color:white;padding:12px max(16px,calc((100% - 1120px)/2));display:flex;align-items:center;justify-content:space-between;gap:12px}
.brand{display:flex;align-items:center;gap:10px;min-width:0}
.logo{width:48px;height:48px;object-fit:cover;border-radius:12px;border:2px solid var(--gold);background:#fff}
.brand-title{font-weight:800;font-size:18px}.tagline{font-size:12px;color:#e4f3e7}
.header-links{display:flex;gap:10px;align-items:center;white-space:nowrap}
.header-links a{color:white;text-decoration:none;font-size:13px}
nav{display:flex;gap:8px;overflow:auto;padding:10px max(12px,calc((100% - 1120px)/2));background:white;border-bottom:1px solid var(--line)}
nav a{white-space:nowrap;text-decoration:none;color:var(--green);background:var(--mint);padding:8px 13px;border-radius:22px;font-size:13px;font-weight:700}
main{max-width:1120px;margin:18px auto;padding:0 12px}
.hero{background:linear-gradient(130deg,#eaf6ed,#fff);border:1px solid #dcebdd;border-radius:20px;padding:22px;margin-bottom:16px}
.hero h1{margin:0 0 5px;font-size:clamp(23px,4vw,34px)}.hero p{margin:0 0 14px;color:var(--muted)}
.search-form{display:grid;grid-template-columns:1fr auto;gap:8px}
input,textarea,select{width:100%;border:1px solid #ccd8ce;background:white;border-radius:10px;padding:11px 12px;font:inherit;color:inherit;margin:4px 0}
textarea{resize:vertical}
.btn{display:inline-flex;justify-content:center;align-items:center;gap:6px;border:0;border-radius:10px;background:var(--green);color:white;padding:10px 15px;text-decoration:none;font:inherit;font-weight:700;cursor:pointer}
.btn.secondary{background:#eaf3ec;color:var(--green)}.btn.gold{background:var(--gold);color:#1f2a20}
.actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}
.filters{display:grid;grid-template-columns:2fr 1fr 1fr auto;gap:8px;margin:12px 0}
.section-head{display:flex;justify-content:space-between;align-items:center;gap:10px;margin:16px 2px 8px}
.section-head h2{font-size:20px;margin:0}
.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}
.card{background:white;border:1px solid var(--line);border-radius:16px;padding:14px;min-width:0;box-shadow:0 3px 12px #173a2010}
.product-image{display:block;width:100%;height:190px;object-fit:cover;border-radius:11px;background:#f0f3f0}
.product-title{font-size:17px;font-weight:800;margin:9px 0 3px;overflow-wrap:anywhere}
.price{font-size:18px;font-weight:800;color:var(--green)}
.meta{font-size:12px;color:var(--muted);display:flex;gap:8px;flex-wrap:wrap}
.description{white-space:pre-wrap;overflow-wrap:anywhere}
.form-card{max-width:760px;margin:0 auto}
.field-label{font-size:13px;font-weight:700;display:block;margin-top:8px}
.notice{padding:11px 13px;border-radius:10px;background:#fff4d6;margin:10px 0}
.flash{padding:11px 13px;border-radius:10px;background:#eaf3ec;margin:10px 0}
.empty{padding:24px;text-align:center;color:var(--muted)}
footer{max-width:1120px;margin:24px auto 0;padding:18px 14px;color:var(--muted);font-size:12px;border-top:1px solid var(--line)}
.badge{display:inline-block;background:#edf6ef;color:#245a35;padding:3px 8px;border-radius:20px;font-size:11px}
@media(max-width:800px){.grid{grid-template-columns:repeat(2,minmax(0,1fr))}.filters{grid-template-columns:1fr 1fr}.filters input:first-child{grid-column:1/-1}}
@media(max-width:520px){header{padding:10px 12px}.tagline{max-width:210px}.grid{grid-template-columns:1fr 1fr;gap:9px}.card{padding:10px}.product-image{height:140px}.product-title{font-size:15px}.price{font-size:16px}.hero{padding:16px}.search-form{grid-template-columns:1fr}.header-links{gap:6px}.filters{grid-template-columns:1fr 1fr}}
</style>
</head>
<body>
<header>
 <div class="brand">
  {% if logo_exists %}<img class="logo" src="{{ url_for('static', filename='1791466021118.jpg') }}" alt="HASAD">{% endif %}
  <div><div class="brand-title">{{ t.name }}</div><div class="tagline">{{ t.tagline }}</div></div>
 </div>
 <div class="header-links">
  <a href="{{ url_for('home', lang='en' if lang == 'ar' else 'ar') }}">{{ 'English' if lang == 'ar' else 'العربية' }}</a>
 </div>
</header>
<nav>
 <a href="{{ url_for('home', lang=lang) }}">{{ t.market }}</a>
 <a href="{{ url_for('add', lang=lang) }}">{{ t.sell }}</a>
 <a href="{{ url_for('plant_health', lang=lang) }}">{{ t.plant }}</a>
 <a href="{{ url_for('map_view', lang=lang) }}">{{ t.map }}</a>
</nav>
<main>
{% for message in get_flashed_messages() %}<div class="flash">{{ message }}</div>{% endfor %}

{% if page == 'home' %}
 <section class="hero">
  <h1>{{ 'السوق الزراعي في مكان واحد' if lang == 'ar' else 'Agriculture marketplace in one place' }}</h1>
  <p>{{ 'اكتشف المنتجات الزراعية، قارن الخيارات، وتواصل مباشرة مع البائع.' if lang == 'ar' else 'Discover agricultural products, compare listings and contact sellers directly.' }}</p>
  <form class="search-form" method="get" action="{{ url_for('home') }}">
   <input type="hidden" name="lang" value="{{ lang }}">
   <input name="q" value="{{ query }}" placeholder="{{ t.search }}" aria-label="{{ t.search }}">
   <button class="btn" type="submit">{{ 'بحث' if lang == 'ar' else 'Search' }}</button>
  </form>
  <div class="actions">
   <a class="btn" href="{{ url_for('add', lang=lang) }}">＋ {{ t.sell }}</a>
   <a class="btn secondary" href="{{ url_for('plant_health', lang=lang) }}">🌿 {{ t.plant }}</a>
  </div>
 </section>
 <form class="filters" method="get" action="{{ url_for('home') }}">
  <input type="hidden" name="lang" value="{{ lang }}">
  <input name="q" value="{{ query }}" placeholder="{{ 'اسم المنتج أو وصفه' if lang == 'ar' else 'Product name or description' }}">
  <select name="category" aria-label="Category">
   <option value="">{{ 'كل الأقسام' if lang == 'ar' else 'All categories' }}</option>
   {% for c in categories %}<option value="{{ c }}" {% if selected_category == c %}selected{% endif %}>{{ c }}</option>{% endfor %}
  </select>
  <input name="place" value="{{ selected_place }}" placeholder="{{ 'المحافظة أو المنطقة' if lang == 'ar' else 'Governorate or area' }}">
  <button class="btn" type="submit">{{ 'تصفية' if lang == 'ar' else 'Filter' }}</button>
 </form>
 <div class="section-head"><h2>{{ 'أحدث الإعلانات' if lang == 'ar' else 'Latest listings' }}</h2><span class="badge">{{ total }} {{ 'إعلان' if lang == 'ar' else 'listings' }}</span></div>
 {% if products %}
 <div class="grid">
 {% for p in products %}
  <article class="card">
   <a href="{{ url_for('product_detail', product_id=p.id, lang=lang) }}" style="text-decoration:none">
    {% if p.image_name %}<img class="product-image" src="{{ url_for('uploaded_file', filename=p.image_name) }}" alt="{{ p.title }}">{% else %}<div class="product-image"></div>{% endif %}
    <div class="product-title">{{ p.title }}</div>
   </a>
   <div class="price">{% if p.price is not none %}{{ '%.2f'|format(p.price) }} {{ p.currency }}{% else %}{{ 'السعر عند التواصل' if lang == 'ar' else 'Contact for price' }}{% endif %}</div>
   <div class="meta"><span>{{ p.category }}</span><span>{{ p.place }}</span></div>
   <p>{{ p.description[:110] }}{% if p.description|length > 110 %}…{% endif %}</p>
   <a class="btn" href="{{ url_for('product_detail', product_id=p.id, lang=lang) }}">{{ 'تفاصيل المنتج' if lang == 'ar' else 'View listing' }}</a>
  </article>
 {% endfor %}
 </div>
 {% else %}<div class="card empty">{{ 'لا توجد إعلانات مطابقة. جرّب تغيير كلمات البحث أو الفلاتر.' if lang == 'ar' else 'No matching listings. Try changing your search or filters.' }}</div>{% endif %}

{% elif page == 'add' %}
 <section class="card form-card">
  <h1>{{ 'إضافة إعلان جديد' if lang == 'ar' else 'Create a listing' }}</h1>
  <p class="meta">{{ 'أدخل معلومات دقيقة؛ الإعلان يخضع لقواعد الاستخدام والمراجعة.' if lang == 'ar' else 'Provide accurate information. Listings are subject to platform rules and review.' }}</p>
  <form method="post" enctype="multipart/form-data">
   <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
   <label class="field-label">{{ 'اسم المنتج' if lang == 'ar' else 'Product name' }}</label>
   <input name="title" maxlength="200" required>
   <label class="field-label">{{ 'القسم' if lang == 'ar' else 'Category' }}</label>
   <select name="category" required>{% for c in categories %}<option value="{{ c }}">{{ c }}</option>{% endfor %}</select>
   <label class="field-label">{{ 'الوصف' if lang == 'ar' else 'Description' }}</label>
   <textarea name="description" maxlength="500" rows="4" required></textarea>
   <div class="filters" style="grid-template-columns:1fr 1fr;margin:0">
    <div><label class="field-label">{{ 'السعر (اتركه فارغًا عند الاتفاق)' if lang == 'ar' else 'Price (leave blank if negotiable)' }}</label><input name="price" type="number" min="0" step="0.01"></div>
    <div><label class="field-label">{{ 'العملة' if lang == 'ar' else 'Currency' }}</label><select name="currency">{% for code,label in currencies.items() %}<option value="{{ code }}" {% if code == 'EGP' %}selected{% endif %}>{{ code }} — {{ label }}</option>{% endfor %}</select></div>
   </div>
   <label class="field-label">{{ 'المحافظة أو المنطقة' if lang == 'ar' else 'Governorate or area' }}</label>
   <input name="place" maxlength="120" required placeholder="{{ 'اكتب الموقع المناسب دون افتراض منطقة محددة' if lang == 'ar' else 'Enter the relevant location' }}">
   <label class="field-label">{{ 'رقم التواصل مع مفتاح الدولة (أرقام فقط)' if lang == 'ar' else 'Contact number with country code (digits only)' }}</label>
   <input name="phone" inputmode="numeric" pattern="[0-9]{8,15}" maxlength="15" required>
   <label class="field-label">{{ 'صورة المنتج (JPG أو PNG، حتى 20 ميجابايت)' if lang == 'ar' else 'Product image (JPG or PNG, up to 20 MB)' }}</label>
   <input type="file" name="file" accept=".jpg,.jpeg,.png,image/jpeg,image/png" required>
   <button class="btn" type="submit">{{ 'نشر الإعلان' if lang == 'ar' else 'Publish listing' }}</button>
  </form>
 </section>

{% elif page == 'detail' %}
 <article class="card form-card">
  {% if product.image_name %}<img class="product-image" style="height:auto;max-height:480px" src="{{ url_for('uploaded_file', filename=product.image_name) }}" alt="{{ product.title }}">{% endif %}
  <h1>{{ product.title }}</h1>
  <div class="price">{% if product.price is not none %}{{ '%.2f'|format(product.price) }} {{ product.currency }}{% else %}{{ 'السعر عند التواصل' if lang == 'ar' else 'Contact for price' }}{% endif %}</div>
  <div class="meta"><span>{{ product.category }}</span><span>{{ product.place }}</span><span>{{ product.created_at }}</span></div>
  <p class="description">{{ product.description }}</p>
  <div class="notice">{{ 'تحقق من تفاصيل المنتج والبائع قبل الدفع. حصاد لا يضمن المعاملات خارج المنصة.' if lang == 'ar' else 'Verify the product and seller before paying. HASAD does not guarantee off-platform transactions.' }}</div>
  <a class="btn" target="_blank" rel="noopener noreferrer" href="https://wa.me/{{ product.phone }}?text={{ whatsapp_text }}">{{ 'تواصل مع البائع عبر واتساب' if lang == 'ar' else 'Contact seller on WhatsApp' }}</a>
  <p><a href="{{ url_for('home', lang=lang) }}">{{ 'العودة إلى السوق' if lang == 'ar' else 'Back to marketplace' }}</a></p>
 </article>

{% elif page == 'plant' %}
 <section class="card form-card">
  <h1>{{ 'صحة النبات' if lang == 'ar' else 'Plant health' }}</h1>
  <p>{{ 'ارفع صورة واضحة للاحتفاظ بها ضمن نموذج التجربة. لا يصدر التطبيق تشخيصًا أو توصية علاجية حتى يتم ربط نظام فحص موثوق.' if lang == 'ar' else 'Upload a clear image for the prototype. The app does not provide a diagnosis or treatment recommendation until a validated analysis system is integrated.' }}</p>
  <form method="post" enctype="multipart/form-data">
   <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
   <label class="field-label">{{ 'صورة النبات' if lang == 'ar' else 'Plant image' }}</label>
   <input type="file" name="file" accept=".jpg,.jpeg,.png,image/jpeg,image/png" required>
   <button class="btn" type="submit">{{ 'رفع الصورة' if lang == 'ar' else 'Upload image' }}</button>
  </form>
  {% if uploaded %}<div class="flash">{{ 'تم حفظ الصورة للتجربة؛ لم يتم تشخيص المرض.' if lang == 'ar' else 'Image saved for testing; no disease diagnosis was made.' }}</div>{% endif %}
 </section>

{% elif page == 'map' %}
 <section class="card">
  <h1>{{ 'خريطة المنتجات' if lang == 'ar' else 'Product map' }}</h1>
  <p>{{ 'سيتم تفعيل الخريطة بعد إضافة إحداثيات جغرافية موثوقة للإعلانات. الموقع النصي وحده لا يكفي لوضع المنتج على الخريطة.' if lang == 'ar' else 'The map will be enabled when listings have reliable geographic coordinates. A text location alone is not sufficient.' }}</p>
 </section>

{% elif page == 'admin' %}
 <section class="card form-card">
 {% if not is_admin %}
  <h1>{{ 'دخول الإدارة' if lang == 'ar' else 'Admin sign in' }}</h1>
  <form method="post">
   <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
   <label class="field-label">{{ 'كلمة المرور' if lang == 'ar' else 'Password' }}</label>
   <input type="password" name="password" autocomplete="current-password" required>
   <button class="btn" type="submit">{{ 'دخول' if lang == 'ar' else 'Sign in' }}</button>
  </form>
 {% else %}
  <h1>{{ 'إدارة الإعلانات' if lang == 'ar' else 'Listing administration' }}</h1>
  <p>{{ total }} {{ 'إعلان' if lang == 'ar' else 'listings' }}</p>
  <form method="post" action="{{ url_for('admin_logout', lang=lang) }}"><input type="hidden" name="csrf_token" value="{{ csrf_token }}"><button class="btn secondary" type="submit">{{ 'تسجيل الخروج' if lang == 'ar' else 'Sign out' }}</button></form>
  {% for p in admin_products %}
   <div style="border-top:1px solid var(--line);padding:12px 0">
    <b>{{ p.title }}</b><div class="meta">{{ p.place }} · {{ p.created_at }}</div>
    <form method="post" action="{{ url_for('delete_product', product_id=p.id, lang=lang) }}" onsubmit="return confirm('تأكيد حذف الإعلان؟')">
     <input type="hidden" name="csrf_token" value="{{ csrf_token }}"><button class="btn" type="submit">{{ 'حذف الإعلان' if lang == 'ar' else 'Delete listing' }}</button>
    </form>
   </div>
  {% endfor %}
 {% endif %}
 </section>
{% endif %}
</main>
<footer>{{ t.name }} · {{ 'منصة مستقلة؛ تفاصيل المنتجات والإعلانات مسؤولية أصحابها.' if lang == 'ar' else 'An independent platform; listing details are the responsibility of their publishers.' }}</footer>
</body>
</html>
"""

@contextmanager
def database():
    conn = sqlite3.connect(DATABASE_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def initialize_database():
    with database() as conn:
        conn.execute("""
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
                image_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_products_created_at
            ON products(created_at DESC)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_products_category
            ON products(category)
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS plant_uploads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                image_name TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)


initialize_database()


def get_language():
    value = request.args.get("lang") or session.get("lang") or "ar"
    if value not in TRANSLATIONS:
        value = "ar"
    session["lang"] = value
    return value


def csrf_token():
    token = session.get("_csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["_csrf_token"] = token
    return token


@app.context_processor
def inject_template_values():
    return {"csrf_token": csrf_token}


@app.before_request
def protect_post_requests():
    if request.method == "POST":
        submitted = request.form.get("csrf_token", "")
        expected = session.get("_csrf_token", "")
        if not expected or not submitted or not hmac.compare_digest(submitted, expected):
            abort(400, description="Invalid or expired form token. Refresh and try again.")


def clean_text(value, limit=MAX_TEXT_LENGTH):
    value = (value or "").strip()
    value = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", value)
    return value[:limit]


def validate_image(file_storage):
    if not file_storage or not file_storage.filename:
        raise ValueError("يرجى اختيار صورة.")
    safe_name = secure_filename(file_storage.filename)
    if "." not in safe_name:
        raise ValueError("امتداد الصورة غير صالح.")
    extension = safe_name.rsplit(".", 1)[1].lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise ValueError("الصيغ المسموحة هي JPG وPNG فقط.")
    header = file_storage.stream.read(12)
    file_storage.stream.seek(0)
    if extension == "png" and not header.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("محتوى الملف لا يطابق صورة PNG.")
    if extension in {"jpg", "jpeg"} and not header.startswith(b"\xff\xd8\xff"):
        raise ValueError("محتوى الملف لا يطابق صورة JPEG.")


def store_image(file_storage, prefix):
    validate_image(file_storage)
    safe_name = secure_filename(file_storage.filename)
    extension = safe_name.rsplit(".", 1)[1].lower()
    image_name = f"{prefix}_{secrets.token_hex(12)}.{extension}"
    image_path = UPLOAD_DIR / image_name
    file_storage.save(image_path)
    digest = hashlib.sha256(image_path.read_bytes()).hexdigest()
    return image_name, image_path, digest


def render_page(page, lang, **context):
    return render_template_string(
        PAGE,
        page=page,
        lang=lang,
        t=TRANSLATIONS[lang],
        logo_exists=(STATIC_DIR / LOGO_RELATIVE_PATH).is_file(),
        categories=CATEGORIES,
        currencies=CURRENCIES,
        **context,
    )


@app.errorhandler(413)
def request_too_large(_error):
    return "حجم الملف يتجاوز الحد المسموح به وهو 20 ميجابايت.", 413


@app.route("/")
def home():
    lang = get_language()
    query = clean_text(request.args.get("q"), 120)
    category = clean_text(request.args.get("category"), 100)
    place = clean_text(request.args.get("place"), 120)

    sql = "SELECT * FROM products WHERE 1=1"
    params = []
    if query:
        sql += " AND (title LIKE ? OR description LIKE ? OR category LIKE ?)"
        wildcard = f"%{query}%"
        params.extend([wildcard, wildcard, wildcard])
    if category in CATEGORIES:
        sql += " AND category = ?"
        params.append(category)
    if place:
        sql += " AND place LIKE ?"
        params.append(f"%{place}%")
    sql += " ORDER BY id DESC LIMIT 100"

    with database() as conn:
        products = conn.execute(sql, params).fetchall()
        total = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]

    return render_page(
        "home", lang, products=products, total=total, query=query,
        selected_category=category, selected_place=place
    )


@app.route("/add", methods=["GET", "POST"])
def add():
    lang = get_language()
    if request.method == "GET":
        return render_page("add", lang)

    title = clean_text(request.form.get("title"), 200)
    category = clean_text(request.form.get("category"), 100)
    description = clean_text(request.form.get("description"), 500)
    place = clean_text(request.form.get("place"), 120)
    phone = re.sub(r"\D", "", request.form.get("phone", ""))
    currency = request.form.get("currency", "EGP")
    raw_price = (request.form.get("price") or "").strip()

    if not title or not description or not place:
        flash("يرجى إكمال الحقول المطلوبة.")
        return redirect(url_for("add", lang=lang))
    if category not in CATEGORIES:
        flash("القسم المحدد غير صالح.")
        return redirect(url_for("add", lang=lang))
    if currency not in CURRENCIES:
        flash("العملة المحددة غير صالحة.")
        return redirect(url_for("add", lang=lang))
    if not re.fullmatch(r"[0-9]{8,15}", phone):
        flash("أدخل رقم تواصل من 8 إلى 15 رقمًا مع مفتاح الدولة.")
        return redirect(url_for("add", lang=lang))

    price = None
    if raw_price:
        try:
            price = float(raw_price)
            if price < 0 or price > 1_000_000_000_000:
                raise ValueError
        except ValueError:
            flash("السعر غير صالح.")
            return redirect(url_for("add", lang=lang))

    try:
        image_name, image_path, image_hash = store_image(request.files.get("file"), "product")
    except ValueError as exc:
        flash(str(exc))
        return redirect(url_for("add", lang=lang))

    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    try:
        with database() as conn:
            conn.execute(
                """INSERT INTO products
                (title, category, description, price, currency, place, phone,
                 image_name, image_hash, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (title, category, description, price, currency, place, phone,
                 image_name, image_hash, created_at),
            )
    except Exception:
        image_path.unlink(missing_ok=True)
        app.logger.exception("Unable to create listing")
        abort(500, description="تعذر حفظ الإعلان. حاول مرة أخرى لاحقًا.")

    flash("تم نشر الإعلان بنجاح.")
    return redirect(url_for("home", lang=lang))


@app.route("/product/<int:product_id>")
def product_detail(product_id):
    lang = get_language()
    with database() as conn:
        product = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    if product is None:
        abort(404)
    from urllib.parse import quote
    message = quote(f"مرحبًا، أود الاستفسار عن المنتج: {product['title']}")
    return render_page("detail", lang, product=product, whatsapp_text=message)


@app.route("/plant-health", methods=["GET", "POST"])
def plant_health():
    lang = get_language()
    uploaded = False
    if request.method == "POST":
        try:
            image_name, _path, _digest = store_image(request.files.get("file"), "plant")
        except ValueError as exc:
            flash(str(exc))
            return redirect(url_for("plant_health", lang=lang))
        with database() as conn:
            conn.execute(
                "INSERT INTO plant_uploads (image_name, created_at) VALUES (?, ?)",
                (image_name, datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")),
            )
        uploaded = True
    return render_page("plant", lang, uploaded=uploaded)


@app.route("/map")
def map_view():
    lang = get_language()
    return render_page("map", lang)


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("admin", lang=get_language()))
        return view(*args, **kwargs)
    return wrapped


@app.route("/admin", methods=["GET", "POST"])
def admin():
    lang = get_language()
    is_admin = bool(session.get("is_admin"))

    if request.method == "POST" and not is_admin:
        configured_password = os.environ.get("HASAD_ADMIN_PASSWORD", "")
        supplied_password = request.form.get("password", "")
        if not configured_password:
            flash("اضبط HASAD_ADMIN_PASSWORD في متغيرات البيئة أولًا.")
        elif hmac.compare_digest(supplied_password, configured_password):
            session.clear()
            session["is_admin"] = True
            session.permanent = True
            return redirect(url_for("admin", lang=lang))
        else:
            flash("بيانات الدخول غير صحيحة.")

    if is_admin:
        with database() as conn:
            admin_products = conn.execute("SELECT * FROM products ORDER BY id DESC").fetchall()
            total = len(admin_products)
    else:
        admin_products, total = [], 0
    return render_page("admin", lang, is_admin=is_admin, admin_products=admin_products, total=total)


@app.route("/admin/logout", methods=["POST"])
@admin_required
def admin_logout():
    session.clear()
    flash("تم تسجيل الخروج.")
    return redirect(url_for("home", lang="ar"))


@app.route("/admin/delete/<int:product_id>", methods=["POST"])
@admin_required
def delete_product(product_id):
    image_name = None
    with database() as conn:
        row = conn.execute("SELECT image_name FROM products WHERE id = ?", (product_id,)).fetchone()
        if row:
            image_name = row["image_name"]
            conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
    if image_name:
        try:
            (UPLOAD_DIR / image_name).unlink(missing_ok=True)
        except OSError:
            app.logger.warning("Unable to remove image for product %s", product_id)
    flash("تم حذف الإعلان إن كان موجودًا.")
    return redirect(url_for("admin", lang=get_language()))


@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    if filename != os.path.basename(filename) or filename.startswith("."):
        abort(404)
    return send_from_directory(UPLOAD_DIR, filename, as_attachment=False, max_age=3600)


if __name__ == "__main__":
    app.run(
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "5000")),
        debug=False,
    )
