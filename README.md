# 🏃‍♂️ Neon Runner — Telegram WebApp 3-Lane Endless Runner (100–700 ⭐ Stars Turniri)

Subway Surfers mexanikasi asosidagi, 3-lane (uch yo'lakli) kiberpank yugurish o'yini va Telegram Mini App platformasi.
Loyiha o'rnatilgan referal tizimi (+1 jon har bir taklif qilingan yangi do'st uchun), 24 soatlik jonlar iqtisodiyoti, anticheat nazorati va 100–700 ⭐ Stars sovrinli turnir tizimi bilan to'liq ta'minlangan.

---

## 🛠 Texnologiyalar Staki

- **Telegram Bot:** Python 3.10+, [aiogram 3.x](https://docs.aiogram.dev/) (asinxron polling, o'zbek tilidagi interfeys, deep-linking).
- **Backend API:** Python, [FastAPI](https://fastapi.tiangolo.com/), Uvicorn, SQLAlchemy 2.0 (SQLite fayl / PostgreSQL), PyJWT, python-dotenv.
- **Frontend / Game Engine:** Vanilla HTML5 + CSS3 (Glassmorphism & Neon) + JavaScript (ES5/ES6).
  - [Three.js r128](https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js) global build (CDN).
  - [GLTFLoader](https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/loaders/GLTFLoader.js) 3D modellar uchun (protsedural zaxira bilan).
  - **Hech qanday build step, npm yoki Webpack talab qilinmaydi!** Oddiy `<script>` teglari.
  - Telegram Mobile WebView uchun moslashuvchan `env(safe-area-inset-*)` dizayn.

---

## 📁 Loyiha Strukturasi

```text
telegram bot 100 stars challange/
├── .env                         # Maxfiy tokenlar va sozlamalar (gitignored)
├── .env.example                 # Sozlamalar shabloni
├── requirements.txt             # Python kutubxonalari
├── database.py                  # SQLAlchemy 2.0 ulanishi va SessionLocal
├── models.py                    # User modeli, 24h jonlar reset va turnir hisoblagichi
├── schema.sql                   # Ma'lumotlar bazasi DDL skripti
│
├── api/
│   ├── __init__.py
│   ├── main.py                  # FastAPI: initData HMAC, JWT, anticheat va reyting
│   ├── database.py
│   └── models.py
│
├── bot/
│   ├── __init__.py
│   └── bot.py                   # aiogram 3.x Telegram boti (/start, /play, /leaderboard, /invite)
│
├── webapp/
│   ├── index.html               # WebApp sahifasi (Menu, HUD, Game Over, Telegram SDK)
│   ├── css/
│   │   └── style.css            # Kiberpank, neon, glassmorphism va safe-area uslubi
│   ├── js/
│   │   └── game.js              # Three.js r128 o'yin dvigateli (fizika, posbon, pooling)
│   └── models/                  # 3D GLTF (.glb) fayllar
│
└── README.md                    # Loyiha qo'llanmasi
```

---

## 🚀 Mahaliy Ishga Tushirish (Local Setup)

### 1. Virtual Muhit (venv) va Kutubxonalarni O'rnatish

Terminalda (PowerShell yoki Bash):
```bash
# Virtual muhit yaratish
python -m venv .venv

# Virtual muhitni faollashtirish:
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# Windows (CMD):
.venv\Scripts\activate.bat
# Linux / macOS:
source .venv/bin/activate

# Kutubxonalarni o'rnatish:
pip install --upgrade pip
pip install -r requirements.txt
```

### 2. `.env` Faylini Sozlash

`.env.example` faylidan nusxa olib, `.env` faylini shakllantiring:
```env
BOT_TOKEN=BotFather_dan_olingan_token
BOT_USERNAME=dabi_plays_bot
WEBAPP_URL=https://your-domain.trycloudflare.com/webapp/
API_URL=https://your-domain.trycloudflare.com

DATABASE_URL=sqlite:///./runner.db

JWT_SECRET=ozingiz_yaratgan_uzun_tasodifiy_maxfiy_kalit
JWT_TTL_SEC=7200

PRIZE_BASE=100
PRIZE_MEGA=700
MEGA_GOAL=15000
TOURNAMENT_DAYS=7
```

---

### 3. Serverlarni Ishga Tushirish

Windowsda `run_all.bat` ni ishga tushiring. U API, Cloudflare tunnel va botni shu tartibda ochadi, yangi HTTPS manzilni `.env` ga yozadi va bot menyusini yangilaydi. Oyna ochiq turishi kerak. To'xtatish: `Ctrl+C` yoki `stop_all.bat`.

Mahalliy test: `http://127.0.0.1:8000/webapp/` (brauzerda mashq rejimi). API: `http://127.0.0.1:8000/health`.

---

## 🤖 Telegram sozlamalari

`cloudflared` kerak: `winget install Cloudflare.cloudflared`. `run_all.bat` bot menyu tugmasini avtomatik yangilaydi.

---

## 🧪 Test va Verifikatsiya Cheklisti

Quyidagi ssenariylar orqali loyihaning barcha muhim funksiyalarini tekshirib olishingiz mumkin:

### 1. Referal Tizimi (+1 Jon va Bir Martalik Mukofot)
- [x] Botga `/start ref_12345` orqali kiring.
- [x] **O'z-o'zini taklif qilish:** Agar foydalanuvchi o'zining shaxsiy ID si bilan kirsa, xabar chiqadi: `"O'zingizning havolangizdan foydalana olmaysiz"` va mukofot berilmaydi.
- [x] **Yangi do'st:** Yangi Telegram foydalanuvchisi taklif havolasi bilan birinchi bor kirganda, taklif qilgan odamga +1 jon qo'shiladi va taklif qilganga botdan tabrik xabari yuboriladi.
- [x] **Qayta kirish:** Oldin ro'yxatdan o'tgan foydalanuvchi qayta ref-link bilan kirsa, takroriy jon berilmaydi (Faqat 1 marta beriladi).

### 2. Jonlar Tugashi va 402 Invite Oqimi
- [x] Foydalanuvchining jonlari soni `0` ga tushganda:
  - Botda `/play` bosilsa, o'yinga kiritmaydi va shaxsiy referal havolani taklif qiladi.
  - WebApp ichida o'yin boshlash tugmasi bosilsa, backend `402 Payment Required` (No lives left) xatosini qaytaradi.
  - Frontend xatoni ushlab, avtomatik ravishda do'st taklif qilish oynasini (`invite dialog`) ochadi.
- [x] **24 soatlik avtomatik tiklanish:** Foydalanuvchi oxirgi resetdan keyin 24 soat o'tib kirsa, uning jonlari avtomatik ravishda yana 3 taga to'ldiriladi.

### 3. Anti-Cheat Nazorati (Soxta Masofalarni Rad Etish)
- [x] O'yin har bir yugurish boshida `/start_game` orqali bir martalik `session_id` oladi.
- [x] **Fizik tezlik chegarasi:** O'yinda maksimal tezlik 30 birlik/sekund. Backend `score > elapsed * 45 + 200` qoidasi bilan hisoblaydi.
- [x] **Tezkor teleport cheat:** Agar kimdir sessiya boshlanganidan 2 soniya ichida 5,000 metr masofani yuborsa:
  ```json
  HTTP 400 Bad Request
  {"detail": "CHEAT_DETECTED: Impossible score for elapsed time"}
  ```
  Natija qabul qilinmaydi va rekordga yozilmaydi.
- [x] **Sessiyani qayta ishlatish (Replay attack):** Bitta `session_id` faqat bir marta ishlatilishi mumkin, takroriy yuborishlar rad etiladi.

### 4. Turnir va MEGA Sovrin Ko'rsatkichi
- [x] Turnir dastlabki foydalanuvchi ro'yxatdan o'tgan paytdan boshlab 7 kunlik muddatni hisoblaydi.
- [x] 15,000 qatnashuvchiga yetmaguncha sovrin: `100 ⭐ Stars`.
- [x] Bazada foydalanuvchilar soni 15,000 taga yetishi bilanoq:
  - WebApp da progress-bar 100% ga yetadi va `700 ⭐ MEGA SOVRIN OCHILDI` yozuvi paydo bo'ladi.
  - Botda `/start` va `/leaderboard` da `🏆 MEGA SOVRIN OCHILDI: 700 ⭐` banneri aks etadi.

---

## 🎮 O'yin Boshqaruvi
- **Chapga / O'ngga:** Ekranni chapga/o'ngga surish (Swipe), klaviaturada `A` / `D` yoki `←` / `→` o'qlari, ekrandagi `◀` `▶` tugmalari.
- **Sakrash:** Ekranni yuqoriga surish yoki ekranga tez bosish (Tap), klaviaturada `W`, `↑` yoki `Space`, ekrandagi `▲` tugmasi.
- **Egilish / Slayd:** Ekranni pastga surish (Swipe down), klaviaturada `S` yoki `↓` o'qi, ekrandagi `▼` tugmasi.
  - *Havo slaydi (Air-slide):* Sakrash paytida pastga bosilsa, qahramon darhol yerga tushadi!
