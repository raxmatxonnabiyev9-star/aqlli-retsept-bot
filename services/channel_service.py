"""Telegram kanal bazasi servisi.

Retseptlar @AqllRetseptBaza kanaliga rasm + caption ko'rinishida saqlanadi.
Telegram Bot API botlarga kanal tarixini to'g'ridan-to'g'ri qidirishga ruxsat
bermaydi, shuning uchun biz mahalliy indeks fayli (recipe_index.json) yuritamiz:
har bir saqlangan retsept hashtaglari va to'liq JSON bilan birga yoziladi.
Qidirishda foydalanuvchi masalliqlarining hashtaglari indeks bilan solishtiriladi.

Bu yondashuv kanalni "bepul baza" sifatida ishlatish imkonini beradi: mos retsept
indeksda topilsa, Claude API qayta chaqirilmaydi.
"""

import json
import logging
import os

from telegram import Bot

logger = logging.getLogger(__name__)

INDEKS_FAYL = "recipe_index.json"

# Qidiruvda retsept mos deb topilishi uchun kerakli minimal hashtag mosligi
MIN_MOSLIK = 2


class ChannelService:
    """Retseptlarni Telegram kanalga saqlash va mahalliy indeks orqali qidirish servisi."""

    def __init__(self, bot: Bot, channel_id: str, indeks_fayl: str = INDEKS_FAYL) -> None:
        """Bot, kanal ID va indeks fayl yo'li bilan servisni ishga tushiradi."""
        self._bot = bot
        self._channel_id = channel_id
        self._indeks_fayl = indeks_fayl
        self._indeks: list[dict] = self._indeksni_yukla()

    # ──────────────────────────────────────────
    # Indeks fayli bilan ishlash
    # ──────────────────────────────────────────

    def _indeksni_yukla(self) -> list[dict]:
        """Mahalliy indeks faylini o'qiydi (mavjud bo'lmasa bo'sh ro'yxat qaytaradi)."""
        if not os.path.exists(self._indeks_fayl):
            return []
        try:
            with open(self._indeks_fayl, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:  # noqa: BLE001
            logger.error("Indeks faylini o'qib bo'lmadi: %s", e)
            return []

    def _indeksni_saqla(self) -> None:
        """Indeksni faylga yozadi."""
        try:
            with open(self._indeks_fayl, "w", encoding="utf-8") as f:
                json.dump(self._indeks, f, ensure_ascii=False, indent=2)
        except Exception as e:  # noqa: BLE001
            logger.error("Indeks faylini saqlab bo'lmadi: %s", e)

    # ──────────────────────────────────────────
    # Qidirish va saqlash
    # ──────────────────────────────────────────

    async def qidir(self, hashtaglar: list[str]) -> dict | None:
        """Berilgan hashtaglar bo'yicha bazadan mos retseptni qidiradi.

        Kamida MIN_MOSLIK ta hashtag mos kelsa, eng ko'p mos kelgan retsept
        (to'liq JSON dict) qaytariladi. Aks holda None.
        """
        try:
            soralgan = set(hashtaglar)
            eng_yaxshi: dict | None = None
            eng_yaxshi_moslik = 0
            for yozuv in self._indeks:
                yozuv_teglari = set(yozuv.get("hashtaglar", []))
                moslik = len(soralgan & yozuv_teglari)
                if moslik > eng_yaxshi_moslik:
                    eng_yaxshi_moslik = moslik
                    eng_yaxshi = yozuv
            if eng_yaxshi and eng_yaxshi_moslik >= MIN_MOSLIK:
                logger.info("Baza: %d ta hashtag mos keldi", eng_yaxshi_moslik)
                return eng_yaxshi.get("retsept")
            return None
        except Exception as e:  # noqa: BLE001
            # Qidiruv xatosi — chaqiruvchi to'g'ridan-to'g'ri Claude ga o'tadi
            logger.error("Kanal qidiruv xatosi: %s", e)
            return None

    async def saqla(self, retsept: dict, caption: str, rasm_url: str | None) -> None:
        """Yangi retseptni kanalga (rasm + caption) joylaydi va indeksga qo'shadi.

        Telegram caption uzunligi cheklangani (1024 belgi) sababli, juda uzun
        caption qisqartiriladi yoki rasm bo'lmasa oddiy matn sifatida yuboriladi.
        """
        hashtaglar = retsept.get("hashtag", "").split()

        try:
            # Caption Telegram cheklovidan oshmasligi uchun qisqartiramiz
            qisqa_caption = caption[:1024]
            if rasm_url:
                await self._bot.send_photo(
                    chat_id=self._channel_id,
                    photo=rasm_url,
                    caption=qisqa_caption,
                    parse_mode="Markdown",
                )
            else:
                await self._bot.send_message(
                    chat_id=self._channel_id,
                    text=caption[:4096],
                    parse_mode="Markdown",
                )
            logger.info("Retsept kanalga saqlandi: %s", retsept.get("taom"))
        except Exception as e:  # noqa: BLE001
            # Kanalga yozish xatosi botni to'xtatmasligi kerak
            logger.error("Kanalga saqlashda xato: %s", e)

        # Mahalliy indeksga qo'shamiz (kanalga yozish muvaffaqiyatidan qat'i nazar)
        self._indeks.append(
            {
                "taom": retsept.get("taom"),
                "hashtaglar": hashtaglar,
                "rasm_url": rasm_url,
                "retsept": retsept,
            }
        )
        self._indeksni_saqla()
