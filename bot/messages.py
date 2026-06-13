"""Botning barcha matn shablonlari (o'zbek tilida) va retseptni formatlash funksiyalari."""

# ─────────────────────────────────────────────
# Statik xabarlar
# ─────────────────────────────────────────────

START = (
    "👨‍🍳 Salom! Men Aqlli Retsept botiman.\n\n"
    "Muzlatgichingizda nima bor?\n\n"
    "✍️ Masalliqlarni yozing:\n"
    "\"tuxum, kartoshka, piyoz, yog', tuz\"\n\n"
    "📸 Yoki muzlatgich rasmini yuboring\n\n"
    "Men sizga faqat bor narsalardan taom taklif qilaman!"
)

KAM_MASALLIQ = "Kamida 2 ta masalliq yozing 🥕"

QAYTA_ISHLANMOQDA = "🔎 Masalliqlaringizni tahlil qilyapman..."

RASM_ISHLANMOQDA = "📸 Rasmni ko'rib chiqyapman..."

RETSEPT_TAYYORLANMOQDA = "👨‍🍳 Retsept tayyorlanyapman, biroz kuting..."

CLAUDE_XATO = "Hozir texnik muammo bor, keyinroq urinib ko'ring 🙏"

TAOM_TOPILMADI = (
    "😔 Bu masalliqlardan mos taom topa olmadim.\n"
    "Yana bir nechta masalliq qo'shib ko'ring."
)

VARIANT_YOQ = "😔 Boshqa variant qolmadi. Yangi masalliqlar yuboring."

SEVIMLI_QOSHILDI = "❤️ Retsept sevimlilarga qo'shildi!"


def variantlar_sarlavhasi(masalliqlar: list[str], soni: int) -> str:
    """Variantlar ro'yxati ustidagi sarlavha matnini qaytaradi."""
    masalliq_str = ", ".join(masalliqlar)
    return (
        f"🍽 Sizning masalliqlaringiz: {masalliq_str}\n\n"
        f"Ushbu masalliqlardan {soni} ta taom tayyorlash mumkin.\n"
        "Qaysi birini pishirmoqchisiz?"
    )


# ─────────────────────────────────────────────
# To'liq retseptni Telegram caption ko'rinishiga keltirish
# ─────────────────────────────────────────────

def _qiyinlik_belgisi(qiyinlik: str) -> str:
    """Qiyinlik darajasiga mos rangli belgi qaytaradi."""
    q = (qiyinlik or "").lower()
    if "oson" in q:
        return "🟢"
    if "o'rta" in q or "orta" in q:
        return "🟡"
    return "🔴"


def retseptni_formatla(r: dict) -> str:
    """Claude qaytargan retsept JSON obyektini Telegram Markdown caption ga aylantiradi.

    `r` — to'liq retsept prompti qaytargan dict (taom, masalliqlar, bosqichlar, ...).
    """
    chiziq = "━━━━━━━━━━━━━━━"
    belgi = _qiyinlik_belgisi(r.get("qiyinlik", ""))

    qatorlar: list[str] = []

    # Sarlavha qismi
    qatorlar.append(f"🍳 *{r.get('taom', 'Taom')}*")
    qatorlar.append(
        f"🌍 {r.get('oshxona', '—')} oshxonasi | "
        f"⏱ {r.get('vaqt_daqiqa', '—')} daqiqa | "
        f"👤 {r.get('porsiya', '—')}"
    )
    qatorlar.append(f"{belgi} Qiyinlik: {r.get('qiyinlik', '—')}")

    # Masalliqlar
    qatorlar.append(chiziq)
    qatorlar.append("📦 *MASALLIQLAR:*")
    for m in r.get("masalliqlar", []):
        qatorlar.append(f"- {m.get('nom', '')} — {m.get('miqdor', '')}")

    # Tayyorlash bosqichlari
    qatorlar.append(chiziq)
    qatorlar.append("👨‍🍳 *TAYYORLASH:*")
    for b in r.get("bosqichlar", []):
        qatorlar.append(f"*{b.get('raqam', '')}. {b.get('sarlavha', '')}*")
        qatorlar.append(b.get("tavsif", ""))
        if b.get("maslahat"):
            qatorlar.append(f"💡 _{b['maslahat']}_")
        if b.get("vaqt_daqiqa"):
            qatorlar.append(f"⏱ _{b['vaqt_daqiqa']} daqiqa_")
        qatorlar.append("")  # bo'sh qator

    # Oshpaz maslahatlari
    maslahatlar = r.get("oshpaz_maslahatlari", [])
    if maslahatlar:
        qatorlar.append(chiziq)
        qatorlar.append("✨ *OSHPAZ MASLAHATLARI:*")
        for ms in maslahatlar:
            qatorlar.append(f"- {ms}")

    # Ozuqaviy qiymat
    qatorlar.append(chiziq)
    qatorlar.append(
        f"🔥 {r.get('kaloriya', '—')} kkal | "
        f"💪 {r.get('oqsil', '—')} | "
        f"🌾 {r.get('uglerod', '—')}"
    )

    return "\n".join(qatorlar)


def retsept_qisqa(r: dict) -> str:
    """Mini App tugmasi bilan yuboriladigan qisqa xabar (sarlavha + asosiy ma'lumot)."""
    belgi = _qiyinlik_belgisi(r.get("qiyinlik", ""))
    return (
        f"🍳 *{r.get('taom', 'Taom')}*\n"
        f"🌍 {r.get('oshxona', '—')} oshxonasi | ⏱ {r.get('vaqt_daqiqa', '—')} daqiqa | "
        f"👤 {r.get('porsiya', '—')}\n"
        f"{belgi} Qiyinlik: {r.get('qiyinlik', '—')}\n\n"
        "To'liq retseptni chiroyli ko'rinishda ochish uchun tugmani bosing 👇"
    )


def kanal_posti_matni(r: dict) -> str:
    """Retseptni kanal bazasiga saqlash uchun matn (retsept + hashtag) tayyorlaydi."""
    matn = retseptni_formatla(r)
    hashtag = r.get("hashtag", "")
    if hashtag:
        matn = f"{matn}\n\n{hashtag}"
    return matn
