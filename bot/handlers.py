"""Telegram handlerlar: /start, matn, rasm va inline tugma bosishlarini boshqaradi.

Servislar (Claude, Unsplash, Channel) main.py da `application.bot_data` ichiga
joylanadi va shu yerdan o'qiladi. Har bir foydalanuvchining holati (masalliqlar,
joriy taom variantlari) `context.user_data` da saqlanadi — shu sababli bot bir
vaqtda ko'p foydalanuvchiga xizmat qila oladi.
"""

import base64
import logging
import os

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from bot import keyboards, messages
from services import recipe_store
from services.ai_service import AIXatosi
from utils import normalizer

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Yordamchi: servislarga qisqa kirish
# ──────────────────────────────────────────────

def _claude(context: ContextTypes.DEFAULT_TYPE):
    """bot_data dan Claude servisini qaytaradi."""
    return context.bot_data["claude"]


def _unsplash(context: ContextTypes.DEFAULT_TYPE):
    """bot_data dan Unsplash servisini qaytaradi."""
    return context.bot_data["unsplash"]


def _channel(context: ContextTypes.DEFAULT_TYPE):
    """bot_data dan kanal bazasi servisini qaytaradi."""
    return context.bot_data["channel"]


# ──────────────────────────────────────────────
# /start
# ──────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/start buyrug'i: salomlashish va qo'llanma matnini yuboradi."""
    context.user_data.clear()
    await update.message.reply_text(messages.START)


# ──────────────────────────────────────────────
# Matnli xabar (masalliqlar ro'yxati)
# ──────────────────────────────────────────────

async def matn_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Foydalanuvchi matn yuborganda — uni masalliqlar ro'yxati deb qabul qiladi."""
    user_input = update.message.text.strip()

    # Offline bo'laklash bilan dastlabki tekshiruv
    bolaklar = normalizer.matnni_bolaklarga_ajrat(user_input)
    if len(bolaklar) < 2:
        await update.message.reply_text(messages.KAM_MASALLIQ)
        return

    holat = await update.message.reply_text(messages.QAYTA_ISHLANMOQDA)

    try:
        # Claude orqali standart nomlarga keltiramiz
        masalliqlar = await _claude(context).normallashtir(user_input)
    except AIXatosi:
        # Claude ishlamasa — offline normallashtirishga tushamiz
        logger.warning("Normallashtirish uchun offline rejimga o'tildi")
        masalliqlar = normalizer.normallashtir(bolaklar)

    # Har ehtimolga qarshi offline normallashtirishni ham qo'llaymiz
    masalliqlar = normalizer.normallashtir(masalliqlar)

    if len(masalliqlar) < 2:
        await holat.edit_text(messages.KAM_MASALLIQ)
        return

    await _variantlarni_korsat(update, context, masalliqlar, holat)


# ──────────────────────────────────────────────
# Rasm (muzlatgich tarkibi)
# ──────────────────────────────────────────────

async def rasm_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Foydalanuvchi rasm yuborganda — Claude Vision orqali masalliqlarni aniqlaydi."""
    holat = await update.message.reply_text(messages.RASM_ISHLANMOQDA)

    try:
        # Eng katta o'lchamdagi rasmni yuklab olamiz
        foto = update.message.photo[-1]
        fayl = await foto.get_file()
        bayt = await fayl.download_as_bytearray()
        rasm_b64 = base64.b64encode(bytes(bayt)).decode("utf-8")

        masalliqlar = await _claude(context).rasmdan_masalliqlar(rasm_b64, "image/jpeg")
        masalliqlar = normalizer.normallashtir(masalliqlar)
    except AIXatosi:
        await holat.edit_text(messages.CLAUDE_XATO)
        return
    except Exception as e:  # noqa: BLE001
        logger.error("Rasmni qayta ishlashda xato: %s", e)
        await holat.edit_text(messages.CLAUDE_XATO)
        return

    if len(masalliqlar) < 2:
        await holat.edit_text(messages.KAM_MASALLIQ)
        return

    await _variantlarni_korsat(update, context, masalliqlar, holat)


# ──────────────────────────────────────────────
# Variantlarni ko'rsatish (matn va rasm uchun umumiy)
# ──────────────────────────────────────────────

async def _variantlarni_korsat(update, context, masalliqlar, holat) -> None:
    """Masalliqlardan taom variantlarini olib, inline tugmalar bilan ko'rsatadi."""
    try:
        taomlar = await _claude(context).variantlar(masalliqlar)
    except AIXatosi:
        await holat.edit_text(messages.CLAUDE_XATO)
        return

    if not taomlar:
        await holat.edit_text(messages.TAOM_TOPILMADI)
        return

    # Holatni foydalanuvchi kontekstida saqlaymiz
    context.user_data["masalliqlar"] = masalliqlar
    context.user_data["taomlar"] = taomlar

    matn = messages.variantlar_sarlavhasi(masalliqlar, len(taomlar))
    klaviatura = keyboards.variantlar_klaviaturasi(taomlar)
    await holat.edit_text(matn, reply_markup=klaviatura)


# ──────────────────────────────────────────────
# Inline tugma bosishlari
# ──────────────────────────────────────────────

async def tugma_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Barcha inline tugma (callback) bosishlarini boshqaradi."""
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("recipe_"):
        await _retseptni_yubor(update, context, int(data.split("_")[1]))
    elif data == "more_variants":
        await _boshqa_variantlar(update, context)
    elif data == "restart":
        await query.message.reply_text(messages.START)
    elif data == "favorite":
        # Sodda variant: faqat tasdiq xabari (sevimlilar ro'yxati kengaytirilishi mumkin)
        await query.answer(messages.SEVIMLI_QOSHILDI, show_alert=True)


async def _boshqa_variantlar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """"Boshqa variantlar" tugmasi: mavjud masalliqlardan yangi taomlar so'raydi."""
    query = update.callback_query
    masalliqlar = context.user_data.get("masalliqlar")
    if not masalliqlar:
        await query.message.reply_text(messages.VARIANT_YOQ)
        return

    try:
        taomlar = await _claude(context).variantlar(masalliqlar)
    except AIXatosi:
        await query.message.reply_text(messages.CLAUDE_XATO)
        return

    if not taomlar:
        await query.message.edit_text(messages.VARIANT_YOQ)
        return

    context.user_data["taomlar"] = taomlar
    matn = messages.variantlar_sarlavhasi(masalliqlar, len(taomlar))
    klaviatura = keyboards.variantlar_klaviaturasi(taomlar)
    await query.message.edit_text(matn, reply_markup=klaviatura)


async def _retseptni_yubor(update: Update, context: ContextTypes.DEFAULT_TYPE, indeks: int) -> None:
    """Tanlangan taom uchun to'liq retseptni (rasm + matn) yuboradi.

    Avval kanal bazasidan qidiradi; topilmasa Claude API ga murojaat qiladi va
    yangi retseptni kanalga saqlaydi.
    """
    query = update.callback_query
    taomlar = context.user_data.get("taomlar", [])
    masalliqlar = context.user_data.get("masalliqlar", [])

    if indeks >= len(taomlar):
        await query.message.reply_text(messages.VARIANT_YOQ)
        return

    taom = taomlar[indeks]
    taom_nomi = taom.get("nom", "Taom")

    await query.message.reply_text(messages.RETSEPT_TAYYORLANMOQDA)
    await context.bot.send_chat_action(
        chat_id=query.message.chat_id, action=ChatAction.TYPING
    )

    # Imzo: saralangan masalliqlar + tanlangan taom (bir xil so'rov → bir xil imzo)
    sig = "|".join(sorted(masalliqlar)) + "::" + taom_nomi.strip().lower()

    # 1) Shu sessiyada keshlangan bo'lsa — qayta ishlatamiz (Gemini chaqirilmaydi)
    retsept = _channel(context).keshdan(sig)

    # 2) Keshda yo'q bo'lsa — Gemini orqali yaratamiz
    if retsept is None:
        try:
            retsept = await _claude(context).toliq_retsept(taom_nomi, masalliqlar)
        except AIXatosi:
            await query.message.reply_text(messages.CLAUDE_XATO)
            return

    # 3) Rasm olamiz va retseptga qo'shamiz (Mini App uni ko'rsatadi)
    rasm_url = await _unsplash(context).taom_rasmi(retsept.get("taom", taom_nomi))
    if rasm_url:
        retsept["rasm_url"] = rasm_url

    chat_id = query.message.chat_id

    # 4) Mini App ochish uchun https manzil bormi? (Render WEBHOOK_URL yoki MINIAPP_URL)
    base = (os.getenv("MINIAPP_URL") or os.getenv("WEBHOOK_URL") or "").rstrip("/")

    if base.startswith("https://"):
        # Retseptni saqlab, Mini App (kartali web interfeys) havolasini yasaymiz
        rid = recipe_store.saqla(retsept)
        app_url = f"{base}/app?id={rid}"
        klaviatura = keyboards.miniapp_klaviaturasi(app_url)
        qisqa = messages.retsept_qisqa(retsept)
        try:
            if rasm_url:
                await context.bot.send_photo(
                    chat_id=chat_id, photo=rasm_url, caption=qisqa,
                    parse_mode="Markdown", reply_markup=klaviatura,
                )
            else:
                await context.bot.send_message(
                    chat_id=chat_id, text=qisqa,
                    parse_mode="Markdown", reply_markup=klaviatura,
                )
        except Exception as e:  # noqa: BLE001
            logger.error("Mini App xabarini yuborishda xato: %s", e)
            await context.bot.send_message(
                chat_id=chat_id, text=qisqa, reply_markup=klaviatura
            )
    else:
        # https hosting yo'q (lokal sinov) — to'liq retsept matn ko'rinishida yuboriladi
        caption = messages.retseptni_formatla(retsept)
        klaviatura = keyboards.retsept_klaviaturasi()
        try:
            if rasm_url:
                await context.bot.send_photo(
                    chat_id=chat_id, photo=rasm_url, caption=caption[:1024],
                    parse_mode="Markdown", reply_markup=klaviatura,
                )
                if len(caption) > 1024:
                    await context.bot.send_message(
                        chat_id=chat_id, text=caption[1024:], parse_mode="Markdown"
                    )
            else:
                await context.bot.send_message(
                    chat_id=chat_id, text=f"🍽\n{caption}"[:4096],
                    parse_mode="Markdown", reply_markup=klaviatura,
                )
        except Exception as e:  # noqa: BLE001 — Markdown/format xatosi
            logger.error("Retseptni yuborishda xato: %s", e)
            await context.bot.send_message(
                chat_id=chat_id, text=caption[:4096], reply_markup=klaviatura
            )

    # 5) Keshga qo'shamiz va (faqat dublikat bo'lmasa) kanalga saqlaymiz
    kanal_matn = messages.kanal_posti_matni(retsept)
    await _channel(context).saqla(retsept, kanal_matn, rasm_url, sig)
