# HASAD _ حصاد V20 - GOOGLE PLAY READY - من مصر للعالم كله - APK + خريطة + إشعارات + ثقة
import os, json, time, re, hashlib
from flask import Flask, request, redirect, session, render_template_string, send_from_directory, abort, Response
from werkzeug.utils import secure_filename
from datetime import datetime

MY_WALLETS = {
    "vodafone": "01043581922", "etisalat": "", "orange": "", "we": "", "instapay": "", "fawry": "", "bank_account": "", "bank_name": "", "paypal": "",
}

app = Flask(__name__)
app.secret_key = "HASAD_V20_GOOGLE_PLAY_EGYPT_WORLD"
app.config['MAX_CONTENT_LENGTH'] = 80 * 1024 * 1024
os.makedirs("static/uploads", exist_ok=True)
DB = "hasad_final.json"
ALLOWED = {'png','jpg','jpeg','mp4','webm','mp3','wav','m4a','ogg','apk'}

WORLD_LANGS = {"ar":"🇪🇬 العربية","en":"🇺🇸 English","tr":"🇹🇷 Türkçe","zh-CN":"🇨🇳 中文","fr":"🇫🇷 Français","de":"🇩🇪 Deutsch","es":"🇪🇸 Español","ru":"🇷🇺 Русский","hi":"🇮🇳 हिन्दी","ur":"🇵🇰 اردو"}

MANUAL = {"ar":{"app":"HASAD _ حصاد","slogan":"من مصر للعالم كله - على جوجل بلاي","home":"🏠 الكل","post":"➕ انشر","map":"🗺️ الخريطة","primo":"⭐ بريمو","admin":"👑 أدمن","set":"⚙️ إعدادات","search":"ابحث..."},"en":{"app":"HASAD _ حصاد","slogan":"From Egypt to World - On Google Play","home":"🏠 All","post":"➕ Post","map":"🗺️ Map","primo":"⭐ Primo","admin":"👑 Admin","set":"⚙️ Settings","search":"Search..."}}

def get_lang(): l=session.get("lang") or request.args.get("lang") or "ar"; return l if l in WORLD_LANGS else "ar"
def get_t(lang): return MANUAL.get(lang, MANUAL["ar"])
def init_db():
    if not os.path.exists(DB): json.dump({"posts":[],"users":{},"free_used":[],"favs":{},"primo_paid":[],"earnings":0,"ratings":{},"referrals":{},"reports":[],"notifications":[]}, open(DB,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
init_db()
def load(): return json.load(open(DB,"r",encoding="utf-8"))
def save(d): json.dump(d, open(DB,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
def clean(t): return re.sub(r'[<>"\']','', (t or ""))[:700].strip()
def is_allowed(f): return '.' in f and f.rsplit('.',1)[1].lower() in ALLOWED
def fraud_check(title, desc, phone, file_path, all_posts):
    score=100; flags=[]
    txt=(title+desc).lower()
    if "بيض" in txt and ("10 جنيه" in txt or "20 جنيه" in txt): score-=40; flags.append("⚠️ سعر بيض رخيص جدا")
    if file_path and os.path.exists(file_path):
        try: h=hashlib.md5(open(file_path,'rb').read()).hexdigest();
        except: h=None
        if h:
            for p in all_posts:
                if p.get("img_hash")==h: score-=50; flags.append("⚠️ صورة مكررة - نصب محتمل")
    if phone in ["0000000000","1234567890"]: score-=100; flags.append("🚫 رقم وهمي")
    level="✅ موثوق" if score>=80 else "⚠️ بحذر" if score>=50 else "🚫 مشبوه"
    return score, level, flags

TEMPLATE = """
<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{t.app}} - {{t.slogan}}</title><link rel="manifest" href="/manifest?lang={{lang}}">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>*{box-sizing:border-box}body{font-family:system-ui;background:#f6faf6;margin:0;padding-bottom:140px}
header{background:linear-gradient(135deg,#0a5a1a,#0a7a20);color:#fff;padding:10px;position:sticky;top:0;z-index:100}
nav{display:flex;gap:4px;padding:6px;background:#fff;overflow:auto;position:sticky;top:64px;z-index:99}
nav a{padding:7px 10px;background:#e8f5e9;border-radius:20px;text-decoration:none;color:#0a7a20;font-size:11px;white-space:nowrap}
nav a.on{background:#0a7a20;color:#fff}
.card{background:#fff;margin:7px;border-radius:16px;padding:11px;box-shadow:0 2px 8px #0001}
.card.primo{border:2px solid gold}.card.fraud{border:2px solid red}
.badge{padding:2px 6px;border-radius:12px;font-size:10px;background:#e8f5e9;display:inline-block}
.badge.pr{background:gold;color:#000;font-weight:bold}.badge.trust{background:#0a7a20;color:#fff}.badge.warn{background:#ff6600;color:#fff}.badge.danger{background:#e60000;color:#fff}
.btn{background:#0a7a20;color:#fff;border:none;padding:9px;border-radius:10px;width:100%;margin-top:4px;cursor:pointer}
.btn.gold{background:linear-gradient(135deg,#FFD700,#FFA500);color:#000;font-weight:bold}
img,video{width:100%;border-radius:12px;max-height:380px;object-fit:cover}
input,textarea,select{width:100%;padding:10px;border-radius:10px;border:1px solid #ccc;margin:3px 0}
#map{height:350px;border-radius:12px;margin:8px 0}
</style>
<div id="google_translate_element" style="position:fixed;bottom:8px;left:8px;z-index:999;background:#fff;padding:5px;border-radius:10px"></div>
<script>function googleTranslateElementInit(){ new google.translate.TranslateElement({pageLanguage:'ar', includedLanguages:'ar,en,tr,zh-CN,fr,de,es,ru,hi,ur', layout:google.translate.TranslateElement.InlineLayout.SIMPLE}, 'google_translate_element');}
function getLoc(){navigator.geolocation.getCurrentPosition(p=>{document.getElementById('lat').value=p.coords.latitude;document.getElementById('lng').value=p.coords.longitude;document.getElementById('loc').innerText='✅ GPS '+p.coords.latitude.toFixed(4);})}
function shareIt(id,title){if(navigator.share){navigator.share({title:title,url:location.origin+'/p/'+id})}else{prompt('Copy:',location.origin+'/p/'+id)}}
if('serviceWorker' in navigator){navigator.serviceWorker.register('/sw.js'); Notification.requestPermission();}
function notifyMe(msg){if(Notification.permission=='granted'){new Notification('HASAD _ حصاد 🌍',{body:msg, icon:'/static/1791466021118.jpg'});}}
</script><script src="//translate.google.com/translate_a/element.js?cb=googleTranslateElementInit"></script>
<link rel="manifest" href="/static/manifest.json">
</head><body>
<header><div style="display:flex;justify-content:space-between;align-items:center">
<div style="display:flex;gap:7px;align-items:center"><img src="/static/1791466021118.jpg" style="width:40px;height:40px;border-radius:10px;object-fit:cover;border:2px solid gold;"><div><b>HASAD _ حصاد</b><br><small style="color:gold;font-size:11px">{{t.slogan}} 🌍</small></div></div>
<select onchange="location='?lang='+this.value" style="width:115px;padding:6px;border-radius:8px;font-size:11px">{% for c,n in world.items() %}<option value="{{c}}" {{'selected' if lang==c}}>{{n}}</option>{% endfor %}</select>
</div></header>
<nav><a href="/?f=all&lang={{lang}}">{{t.home}}</a><a href="/map?lang={{lang}}">{{t.map}}</a><a href="/?f=trusted&lang={{lang}}">✅ موثوق</a><a href="/add?lang={{lang}}">{{t.post}}</a><a href="/primo?lang={{lang}}">{{t.primo}}</a><a href="/admin?lang={{lang}}">{{t.admin}}</a><a href="/myfavs?lang={{lang}}">⭐</a><a href="/settings?lang={{lang}}">{{t.set}}</a></nav>
<div class="card" style="background:linear-gradient(135deg,#0a5a1a,#2ecc71);color:#fff"><b>HASAD _ حصاد - {{t.slogan}} 🌍📱</b><br><small>✅ جاهز لجوجل بلاي - 🗺️ خريطة - 🔔 إشعارات - 🛡️ كشف غش - 💰 كل المحافظ سوا</small><br><button onclick="notifyMe('🔔 الإشعارات شغالة - هتعرف أي بيضة جديدة في الدلنجات!')" style="background:#fff;color:#0a7a20;padding:6px;border-radius:8px;border:none;margin-top:4px">🔔 فعل الإشعارات</button><form action="/ai?lang={{lang}}" method="post" style="margin-top:6px"><input name="q" placeholder="{{t.search}}" required><button class="btn" style="background:#fff;color:#0a7a20">Ask حصاد الذكي</button></form>{% if ans %}<div style="background:#fff;color:#000;padding:8px;border-radius:8px;margin-top:6px">{{ans}}</div>{% endif %}</div>
{% for p in posts %}<div class="card {{'primo' if p.primo else ''}} {{'fraud' if p.trust_score|default(100)<50 else ''}}">
{% if p.primo %}<span class="badge pr">⭐ Primo</span>{% endif %}{% if p.trust_score>=80 %}<span class="badge trust">✅ {{p.trust_level}} {{p.trust_score}}%</span>{% elif p.trust_score>=50 %}<span class="badge warn">{{p.trust_level}} {{p.trust_score}}%</span>{% else %}<span class="badge danger">{{p.trust_level}} {{p.trust_score}}%</span>{% endif %}<span class="badge">{{p.market_type}}</span><br><b>{{p.title}}</b><br><small>{{p.user}} | {{p.place}} | {{p.time}} | ⭐{{p.rating|default('5.0')}} | 👁️{{p.views|default(0)}}</small>{% if p.flags %}<div style="background:#fff3cd;padding:6px;border-radius:8px;margin:4px 0;font-size:11px">{% for f in p.flags %}<div>{{f}}</div>{% endfor %}</div>{% endif %}<br>{{p.desc}}<br><br>{% if p.file %}{% if 'فيديو' in p.type_media %}<video controls src="/{{p.file}}"></video>{% elif 'صوت' in p.type_media %}<audio controls src="/{{p.file}}" style="width:100%"></audio>{% else %}<img src="/{{p.file}}">{% endif %}{% endif %}{% if p.lat %}<a href="https://www.google.com/maps/dir/?api=1&destination={{p.lat}},{{p.lng}}" target="_blank"><button class="btn">🧭 GPS</button></a>{% endif %}<div style="background:#f0f8ff;padding:6px;border-radius:8px;margin:4px 0;font-size:10px;text-align:center">💳 كل المحافظ سوا | 🔒 لا تدفع قبل فيديو | 💰 عمولة 2% محفوظة</div><div style="display:flex;gap:4px;flex-wrap:wrap"><a href="https://wa.me/{{p.phone}}?text=HASAD:{{p.title}} - ثقة {{p.trust_score}}% - فيديو؟" style="flex:1"><button class="btn">💬 واتساب</button></a><a href="/rate/{{p.id}}/5?lang={{lang}}"><button class="btn" style="background:#FFD700;color:#000;width:auto">⭐</button></a><a href="/report/{{p.id}}?lang={{lang}}"><button class="btn" style="background:#e60000;width:auto">🚩</button></a><button onclick="shareIt('{{p.id}}','{{p.title}}')" class="btn" style="background:#e2e3e5;color:#000;width:auto">📤</button></div></div>{% endfor %}
<script>if("serviceWorker" in navigator){navigator.serviceWorker.register("/static/sw.js");}</script>
</body></html>
"""

@app.route("/")
def home():
    lang=get_lang(); session["lang"]=lang; t=get_t(lang); db=load(); f=request.args.get("f","all")
    posts=sorted(db["posts"], key=lambda x:(x.get("primo",False), x.get("trust_score",100), x.get("ts",0)), reverse=True)
    if f=="trusted": posts=[p for p in posts if p.get("trust_score",0)>=80]
    for p in posts[:50]: p["views"]=p.get("views",0)+1
    save(db); return render_template_string(TEMPLATE, posts=posts[:70], f=f, ans=None, t=t, lang=lang, world=WORLD_LANGS)

@app.route("/map")
def map_view():
    lang=get_lang(); t=get_t(lang); db=load()
    posts=[p for p in db["posts"] if p.get("lat")]
    markers=",".join([f"{{lat:{p.get('lat')},lng:{p.get('lng')},title:'{p.get('title','')[:20]}',id:'{p.get('id')}''}}" for p in posts[:100]])
    return f"""<body dir="rtl"><h2>🗺️ خريطة HASAD _ حصاد - من مصر للعالم كله</h2><div id="map"></div><script>var map=L.map('map').setView([30.6,30.7],9); L.tileLayer('https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png').addTo(map); var ms=[{markers}]; ms.forEach(m=>{{L.marker([m.lat,m.lng]).addTo(map).bindPopup(`<b>${{m.title}}</b><br><a href='/p/${{m.id}}'>عرض</a>`);}});</script><br><a href="/?lang={lang}">🏠 رجوع HASAD _ حصاد</a></body>"""

@app.route("/ai", methods=["POST"])
def ai():
    lang=get_lang(); t=get_t(lang); q=clean(request.form.get("q",""))
    ans=f"🤖 HASAD: {q} -> بيض 120ج، لبن 28ج، سمن 300ج. 🗺️ شوف الخريطة - 🔔 فعل الإشعارات - 🛡️ اطلب فيديو قبل الدفع - من مصر للعالم كله"
    db=load(); return render_template_string(TEMPLATE, posts=sorted(db["posts"], key=lambda x:x.get("ts",0), reverse=True)[:6], f="all", ans=ans, t=t, lang=lang, world=WORLD_LANGS)

@app.route("/login", methods=["GET","POST"])
def login():
    lang=get_lang()
    if request.method=="POST":
        phone=re.sub(r'\D','',request.form.get("phone","")); acc=clean(request.form.get("acc_type","ضيف")); uid=phone[-4:] if phone else "EG"; session["user"]=f"{acc}-{uid}"; session["acc_type"]=acc; session["lang"]=lang; db=load(); db["users"][session["user"]]={"acc":acc,"phone":phone}; save(db); return redirect(f"/?lang={lang}")
    return f"""<body dir="rtl"><h3>HASAD _ حصاد - Login</h3><form method="post"><select name="acc_type"><option>فلاح</option><option>تاجر</option><option>شركة</option><option>ضيف</option></select><input name="phone" placeholder="01xxxxxxxxx" required><button style="width:100%;padding:12px;background:#0a7a20;color:#fff">دخول - HASAD _ حصاد</button></form></body>"""
@app.route("/add", methods=["GET","POST"])
def add():
    lang=get_lang(); t=get_t(lang)
    if "user" not in session: session["user"]="ضيف-مصر"
    if request.method=="GET":
        return f"""<body dir="rtl" style="padding:12px"><h3>{t['post']} - HASAD _ حصاد V20 - خريطة + ثقة</h3><form method="post" enctype="multipart/form-data"><input name="title" required placeholder="عنوان"><textarea name="desc" required placeholder="وصف + سعر"></textarea><input name="place" value="الدلنجات"><input name="phone" required placeholder="واتساب"><input type="file" name="file" required accept="image/*,video/*"><input type="hidden" id="lat" name="lat"><input type="hidden" id="lng" name="lng"><p id="loc"></p><button type="button" onclick="getLoc()">📍 GPS للخريطة</button><button style="width:100%;padding:12px;background:#0a7a20;color:#fff">نشر - يظهر على الخريطة + كشف غش - من مصر للعالم كله</button></form><script>function getLoc(){{navigator.geolocation.getCurrentPosition(p=>{{document.getElementById('lat').value=p.coords.latitude;document.getElementById('lng').value=p.coords.longitude;document.getElementById('loc').innerText='✅ GPS';}})}}</script></body>"""
    db=load(); f=request.form; pid=str(int(time.time()*1000)); fp=None; media="نص"; file=request.files.get("file"); img_hash=None
    if file and file.filename and is_allowed(file.filename):
        fn=secure_filename(f"{pid}_{file.filename}"); pth=os.path.join("static/uploads", fn); file.save(pth); fp=pth; ext=fn.rsplit('.',1)[1].lower(); media="فيديو" if ext in ['mp4','webm'] else "صورة"
        try: img_hash=hashlib.md5(open(pth,'rb').read()).hexdigest()
        except: pass
    score, level, flags = fraud_check(clean(f.get("title")), clean(f.get("desc")), re.sub(r'\D','',f.get("phone","")), fp, db["posts"])
    item={"id":pid,"ts":time.time(),"title":clean(f.get("title")),"desc":clean(f.get("desc")),"place":clean(f.get("place")),"phone":re.sub(r'\D','',f.get("phone","")),"cat":"market","market_type":"عام","gov":"مصر","user":session.get("user","ضيف"),"time":datetime.now().strftime("%d/%m %H:%M"),"likes":0,"views":0,"file":fp,"type_media":media,"lat":clean(f.get("lat")),"lng":clean(f.get("lng")),"primo":False,"trust_score":score,"trust_level":level,"flags":flags,"img_hash":img_hash,"rating":5.0,"rating_count":0}
    db["posts"].append(item); db.setdefault("notifications",[]).append({"title":item["title"],"time":datetime.now().strftime("%H:%M")}); save(db); return redirect(f"/?lang={lang}")

@app.route("/rate/<pid>/<int:stars>")
def rate(pid, stars): db=load(); [exec("p['rating_count']=p.get('rating_count',0)+1; p['rating']=(p.get('rating',5.0)*(p['rating_count']-1)+stars)/p['rating_count']", {}, {"p":p}) for p in db["posts"] if p["id"]==pid]; save(db); return redirect(request.referrer or "/")
@app.route("/report/<pid>")
def report(pid): db=load(); db.setdefault("reports",[]).append({"id":pid}); [p.__setitem__('trust_score',max(0,p.get('trust_score',80)-15)) for p in db["posts"] if p["id"]==pid]; save(db); return redirect(request.referrer or "/")
@app.route("/like/<pid>")
def like(pid): db=load(); [p.__setitem__('likes',p.get('likes',0)+1) for p in db["posts"] if p["id"]==pid]; save(db); return redirect(request.referrer or "/")
@app.route("/primo", methods=["GET","POST"])
def primo():
    lang=get_lang(); t=get_t(lang); db=load(); uid=session.get("user","ضيف")
    if request.method=="POST":
        if request.form.get("free")=="1" and uid not in db.get("free_used",[]):
            session["is_primo"]=True; db.setdefault("free_used",[]).append(uid); save(db); return f"<h1>🎉 بريمو ON - HASAD _ حصاد</h1><a href='/?lang={lang}'>رجوع</a>"
        if request.form.get("paid")=="1": db.setdefault("primo_paid",[]).append({"user":uid}); db["earnings"]=db.get("earnings",0)+49; save(db); return f"<h1>✅ تم - 49ج - HASAD _ حصاد</h1><a href='/admin'>أدمن</a>"
    return f"""<body dir="rtl"><h2>⭐ Primo 49ج - HASAD _ حصاد - من مصر للعالم كله - جوجل بلاي</h2><div style="background:#fff;padding:12px"><form method="post"><input type="hidden" name="free" value="1"><button>🎁 مجاني 30 يوم</button></form><br><form method="post"><select name="method"><option>فودافون كاش {MY_WALLETS['vodafone']}</option><option>اتصالات كاش</option><option>أورنج</option><option>وي</option><option>إنستاباي</option><option>PayPal عالمي</option></select><input type="hidden" name="paid" value="1"><button style="background:gold">✅ دفعت 49ج</button></form></div><a href="/?lang={lang}">🏠 رجوع</a></body>"""

@app.route("/admin")
def admin():
    lang=get_lang(); db=load()
    total=len(db["posts"]); earn=db.get("earnings",0)
    html="".join([f"<div style='background:#fff;padding:6px;margin:3px'>{p['title']} - {p.get('trust_score',100)}% <a href='/del/{p['id']}'>🗑️</a></div>" for p in db["posts"][:30]])
    return f"<body dir='rtl'><h2>👑 أدمن V20 - HASAD _ حصاد - جوجل بلاي</h2><b>منشورات: {total} - أرباح: {earn}ج</b><br><br>{html}<br><a href='/?lang={lang}'>🏠</a> | <a href='/build_apk_info?lang={lang}'>📱 كيف أبني APK؟</a></body>"

@app.route("/build_apk_info")
def apk_info():
    lang=get_lang()
    return f"""<body dir="rtl" style="padding:12px"><h2>📱 كيف تحول HASAD _ حصاد لتطبيق جوجل بلاي؟</h2>
    <div style="background:#fff;padding:12px;border-radius:12px">
    <h3>الطريقة السهلة (PWA - شغالة دلوقتي):</h3>
    <p>1. افتح موقعك في كروم<br>2. دوس 3 نقط فوق -> Add to Home Screen<br>3. بقى تطبيق رسمي!</p>
    <h3>الطريقة الاحترافية (APK لجوجل بلاي):</h3>
    <p>1. في Pydroid اعمل:<br><code>pip install buildozer<br>buildozer init</code><br>2. عدل buildozer.spec: حط <b>com.hasad.egypt.world</b><br>3. شغّل: <code>buildozer android debug</code><br>4. هتلاقي ملف hasad.apk في bin/ - ارفعه على <b>play.google.com/console</b><br>5. حساب المطور 25$ مرة واحدة - واسم التطبيق: <b>HASAD _ حصاد - من مصر للعالم كله</b></p>
    <p style="background:#d4edda;padding:8px;border-radius:8px">✅ تطبيقك جاهز لجوجل بلاي - فيه خريطة وإشعارات وكشف غش وكل المحافظ - من مصر للعالم كله!</p>
    </div><br><a href="/?lang={lang}">🏠 HASAD _ حصاد</a></body>"""

@app.route("/sw.js")
def sw(): return Response("self.addEventListener('install',e=>{self.skipWaiting();}); self.addEventListener('fetch',e=>{e.respondWith(fetch(e.request).catch(()=>caches.match(e.request)));});", mimetype="application/javascript")
@app.route("/manifest")
def mani(): lang=get_lang(); return {"name":"HASAD _ حصاد - من مصر للعالم كله - جوجل بلاي","short_name":"HASAD _ حصاد","start_url":f"/?lang={lang}","display":"standalone","background_color":"#0a5a1a","theme_color":"#0a7a20","icons":[{"src":"/static/1791466021118.jpg","sizes":"512x512","type":"image/jpeg"}]}
@app.route("/static/uploads/<path:fn>")
def up(fn):
    if ".." in fn: abort(400)
    return send_from_directory("static/uploads", fn)
@app.route("/p/<pid>")
def single(pid): lang=get_lang(); t=get_t(lang); db=load(); p=next((x for x in db["posts"] if x["id"]==pid), None); return render_template_string(TEMPLATE, posts=[p] if p else [], f="all", ans=None, t=t, lang=lang, world=WORLD_LANGS) if p else "Not found"
@app.route("/del/<pid>")
def delete_post(pid): db=load(); db["posts"]=[p for p in db["posts"] if p["id"]!=pid]; save(db); return redirect("/admin")
@app.route("/settings", methods=["GET","POST"])
def settings_page():
    lang=get_lang()
    if request.method=="POST": session["lang"]=request.form.get("lang",lang); return redirect(f"/settings?lang={session['lang']}&saved=1")
    return f"""<body dir="rtl"><h2>⚙️ HASAD _ حصاد V20 - إعدادات جوجل بلاي</h2><form method="post"><select name="lang"><option value="ar">العربية</option><option value="en">English</option></select><button>حفظ</button></form><br><a href="/build_apk_info?lang={lang}">📱 كيف أبني APK لجوجل بلاي؟</a></body>"""

if __name__=="__main__":
    print("✅ HASAD _ حصاد V20 GOOGLE PLAY READY - http://localhost:5000 - من مصر للعالم كله")
    app.run(host="0.0.0.0", port=5000)