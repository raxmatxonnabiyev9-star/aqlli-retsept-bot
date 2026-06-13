# 🍳 Aqlli Retsept Bot

**@AqllRetseptBot** — muzlatgichingizda bor masalliqlardan tayyorlanadigan
taomlarni topib beruvchi aqlli Telegram bot.

Foydalanuvchi o'zida bor masalliqlarni yozadi yoki muzlatgich rasmini yuboradi,
bot esa **faqat shu masalliqlardan** tayyorlanishi mumkin bo'lgan taomlarni
taklif qiladi va to'liq retsept beradi (bosqichma-bosqich tushuntirish, oshpaz
maslahatlari, kaloriya va h.k.).

Maqsadli auditoriya: O'zbekistondagi uy bekalari va talabalar. Barcha matnlar
o'zbek tilida.

---

## ✨ Imkoniyatlari

- ✍️ **Matn orqali** masalliq kiritish (`tuxum, kartoshka, piyoz`)
- 📸 **Rasm orqali** — muzlatgich rasmidan masalliqlarni Gemini Vision aniqlaydi
- 🤖 Masalliqlarni standart o'zbek nomlariga **normallashtirish**
- 🍽 Har bir so'rovga **3 ta turli taom** varianti (o'zbek, yevropa, osiyo)
- 📖 To'liq retsept: masalliqlar, bosqichlar, maslahatlar, ozuqaviy qiymat
- 💾 Retseptlar **Telegram kanal bazasiga** saqlanadi — keyingi safar bepul qaytariladi
- ☁️ **Webhook rejimi** — Render.com bepul tier'da to'xtamasdan ishlaydi
- ⚡️ To'liq **async**, bir vaqtda ko'p foydalanuvchiga xizmat qiladi

---

## 🗂 Loyiha strukturasi

```
aqlli_retsept/
├── main.py                  # Bot + Flask webhook server
├── bot/
│   ├── handlers.py          # Telegram handlerlar
│   ├── keyboards.py         # Inline tugmalar
│   └── messages.py          # Matn shablonlari + retsept formatlash
├── services/
│   ├── ai_service.py        # Google Gemini API
│   ├── unsplash_service.py  # Rasm olish
│   └── channel_service.py   # Telegram kanal baza
├── utils/
│   └── normalizer.py        # Masalliqlarni normallashtirish
├── render.yaml              # Render sozlamalari
├── Procfile                 # web: python main.py
├── .env.example
├── requirements.txt
└── README.md
```

---

## 🚀 Bosqichma-bosqich qo'llanma

### 1. Telegram bot yaratish
1. [@BotFather](https://t.me/BotFather) ga o'ting
2. `/newbot` buyrug'ini yuboring
3. **Nom:** `Aqlli Retsept`
4. **Username:** `AqllRetseptBot`
5. Berilgan **BOT_TOKEN** ni saqlang

### 2. Telegram kanal yaratish (baza)
1. Yangi **kanal** oching: `@AqllRetseptBaza` (yopiq qiling)
2. Kanal sozlamalari → **Administrators** → botingizni admin qiling (post yuborish huquqi bilan)
3. **CHANNEL_ID** ni oling:
   - Public kanal: `@AqllRetseptBaza`
   - Private kanal: `-100...` ko'rinishidagi raqamli ID

### 3. Gemini API key olish
1. [aistudio.google.com](https://aistudio.google.com) ga o'ting
2. Google hisobingiz bilan kiring
3. **Get API Key** tugmasini bosing
4. **Create API Key** tugmasini bosing
5. Kalitni nusxalab `.env` ga joylang: `GEMINI_API_KEY=sizning_kalitingiz`

> **Bepul limit:** 15 so'rov/daqiqa · 1500 so'rov/kun · 1,000,000 token/kun —
> boshlang'ich bot uchun yetarli.

### 4. Unsplash API key olish
1. [unsplash.com/developers](https://unsplash.com/developers) ga o'ting
2. **New Application** yarating
3. **Access Key** ni saqlang → **UNSPLASH_ACCESS_KEY**
   - (Ixtiyoriy — kalit bo'lmasa bot rasmsiz ishlaydi)

### 5. GitHub'ga yuklash
1. [github.com](https://github.com) da yangi repo yarating
2. Kodni push qiling:
   ```bash
   git init
   git add .
   git commit -m "Aqlli Retsept Bot"
   git remote add origin <repo-url>
   git push -u origin main
   ```
   > ⚠️ `.env` fayli `.gitignore` da — u **hech qachon** gitga ketmaydi.

### 6. Render.com'da deploy qilish
1. [render.com](https://render.com) ga GitHub bilan kiring
2. **New → Web Service** → GitHub repongizni tanlang
3. Render `render.yaml` ni o'qiydi (build/start avtomatik)
4. **Environment** bo'limida o'zgaruvchilarni kiriting:
   ```
   BOT_TOKEN            = ...
   GEMINI_API_KEY       = ...
   UNSPLASH_ACCESS_KEY  = ...
   CHANNEL_ID           = @AqllRetseptBaza
   WEBHOOK_URL          = (hozircha bo'sh qoldiring)
   ```
5. **Deploy** tugmasini bosing
6. Deploy tugagach Render sizga URL beradi (masalan `https://aqlli-retsept-bot.onrender.com`).
   Shu URL'ni **WEBHOOK_URL** ga yozing va qayta deploy qiling.
   - Bot ishga tushganda webhook'ni avtomatik ro'yxatdan o'tkazadi:
     `https://<url>.onrender.com/webhook/<BOT_TOKEN>`

### 7. Ishga tushirishni tekshirish
1. Telegram'da botga `/start` yuboring
2. `tuxum, kartoshka, piyoz` deb yozing
3. Bot **3 ta variant** taklif qilishi kerak ✅

---

## 🧪 Lokal sinash (ixtiyoriy)

`WEBHOOK_URL` bo'sh bo'lsa, bot avtomatik **polling** rejimida ishlaydi — Render'siz,
o'z kompyuteringizda sinash uchun qulay:

```bash
python -m venv venv
# Windows:  venv\Scripts\activate
# Linux/macOS:  source venv/bin/activate

pip install -r requirements.txt
cp .env.example .env        # va kalitlarni to'ldiring (WEBHOOK_URL ni bo'sh qoldiring)

python main.py
```

---

## ⚠️ Xato holatlari

| Holat | Bot javobi |
|-------|-----------|
| Masalliq 2 tadan kam | `Kamida 2 ta masalliq yozing 🥕` |
| Gemini API xatosi | `Hozir texnik muammo bor, keyinroq urinib ko'ring 🙏` |
| Unsplash rasm topilmasa | Rasmsiz, faqat matn yuboriladi |
| Kanal qidiruv xatosi | To'g'ridan-to'g'ri Gemini API'ga o'tadi |
| JSON parse xatosi | Gemini'ga qayta so'rov (maks. 2 marta) |

---

## 🧰 Texnik stack

| Komponent | Texnologiya |
|-----------|-------------|
| Til | Python 3.11+ |
| Telegram | python-telegram-bot 20.7 (async) |
| Web server | Flask 3.0 (webhook) |
| AI | Google Gemini (`gemini-2.5-flash`) |
| Rasmlar | Unsplash API |
| Baza | Telegram kanal + mahalliy indeks |
| HTTP | httpx (async) |
| Hosting | Render.com (bepul tier, webhook) |

> **Eslatma:** Telegram Bot API botlarga kanal tarixini qidirishga ruxsat
> bermaydi, shuning uchun bot saqlangan retseptlar indeksini `recipe_index.json`
> faylida yuritadi. Render bepul tier'da disk vaqtinchalik (ephemeral) bo'lgani
> sababli, doimiy baza kerak bo'lsa keyinroq PostgreSQL'ga o'tkazish tavsiya etiladi.

---

## 📄 Litsenziya

Shaxsiy / ta'limiy maqsadlar uchun erkin foydalaning.
