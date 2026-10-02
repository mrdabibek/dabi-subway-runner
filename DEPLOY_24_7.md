# 🚀 Subway Runner — 24/7 Bepul Serverga Joylash Qo'llanmasi (Render.com)

Bu usul orqali o'yin va bot **kompyuteringiz o'chirilgan bo'lsa ham 24/7/365 uzluksiz** ishlaydi. Havola hech qachon o'zgarmaydi va yangilanib turishi shart bo'lmaydi!

---

### 1-QADAM: GitHub'ga yuklash (1 daqiqa)

1. [github.com](https://github.com) ga kiring va **New Repository** tugmasini bosing:
   * Repository nomi: `dabi-subway-runner`
   * Public yoki Private qilib oching.
2. Kompyuteringiz terminalida quyidagi 2 ta buyruqni bering (USERNAME o'rniga o'z GitHub nomingizni yozasiz):
   ```powershell
   git remote add origin https://github.com/USERNAME/dabi-subway-runner.git
   git push -u origin master
   ```

---

### 2-QADAM: Render.com ga ulash (2 daqiqa)

1. [render.com](https://render.com) saytiga kiring va **GitHub orqali bepul kiring**.
2. Yuqori o'ng burchakdagi **«New +»** tugmasini bosib, **«Web Service»** ni tanlang.
3. Yangi ochgan `dabi-subway-runner` repositoryingizni tanlang (**Connect**).
4. Quyidagi sozlamalarni kiriting (yoki Render ularni `render.yaml` orqali avtomatik to'ldiradi):
   * **Name:** `dabi-subway-runner`
   * **Region:** `Frankfurt (EU Central)`
   * **Branch:** `master`
   * **Runtime:** `Python 3`
   * **Build Command:** `pip install -r requirements.txt`
   * **Start Command:** `python run_all.py`
   * **Instance Type:** `Free` (0$ / bepul)
5. Pastdagi **Environment Variables** (Atrof-muhit o'zgaruvchilari) bo'limiga quyidagilarni kiriting:
   * `BOT_TOKEN`: `8915668770:AAEso8H_bd43ROzfKNUojzX1JY_3qSFQPok`
   * `BOT_USERNAME`: `dabi_plays_bot`
   * `JWT_SECRET`: `wb060KUY9wCTgFDM8EagFTLaUkBu0u4Qgz7i10EO7x8`
6. **«Deploy Web Service»** tugmasini bosing!

---

### 3-QADAM: Doimiy Havolani O'rnatish

Render loyihangizni bir necha daqiqada yig'ib (build qilib), sizga doimiy rasmiy havola beradi:
Masalan: `https://dabi-subway-runner.onrender.com`

Render bergan shu havolani oling va Render'dagi **Environment Variables** ga oxirgi o'zgaruvchini qo'shing:
* `WEBAPP_URL`: `https://dabi-subway-runner.onrender.com/webapp/`
* `API_URL`: `https://dabi-subway-runner.onrender.com`

**TAMOM! 🎉**
- Bot o'zining Telegram Chat Menu Button'ini (`▶️ O'ynash`) avtomatik yangilaydi.
- Bot va WebApp 24/7/365 to'xtovsiz ishlaydi!
- Kompyuteringizni xohlasangiz o'chirib qo'ying — o'yin baribir ishlayveradi.

---

### ⚡ 24/7 Uxlamaslik Tizimi (Keep-Alive)
Render'ning bepul tarifi 15 daqiqa murojaat bo'lmasa serverni uyquga ketkazishi mumkin.
Buning oldini olish uchun biz yozgan `run_all.py` fayli o'z-o'zini har 10 daqiqada avtomatik uyg'otib turadi (`Keep-Alive`).
Qo'shimcha kafolat uchun [uptimerobot.com](https://uptimerobot.com) (bepul) saytiga kirib, `https://dabi-subway-runner.onrender.com/health` manziliga 5 daqiqalik bepul monitor ulab qo'ysangiz, server umrbod 1 soniya ham uxlamasdan ishlaydi!
