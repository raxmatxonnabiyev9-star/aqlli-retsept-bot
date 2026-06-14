"""Telegram kanal bazasi servisi (dublikatlarsiz, doimiy indeks bilan).

Retseptlar @AqllRetseptBaza kanaliga rasm + caption ko'rinishida saqlanadi.
Telegram Bot API botlarga kanal tarixini qidirishga ruxsat bermaydi, shuning
uchun bot indeksni kanaldagi **pinned (qadalgan) xabarda** JSON sifatida yuritadi:
har bir saqlangan retseptning "imzosi" (signature) shu yerga yoziladi.

- Imzo (sig) = saralangan masalliqlar + tanlangan taom nomi. Bir xil so'rov →
  bir xil imzo → dublikat aniqlanadi.
- Pinned xabar Render "uyqu"sidan (restart) keyin ham saqlanadi — shuning uchun
  bir xil retsept kanalga qayta tashlanmaydi.
- To'liq retseptlar shu sessiya davomida xotirada keshlanadi (Gemini'ni qayta
  chaqirmaslik uchun); restart'dan keyin kesh tozalanadi, lekin dublikat baribir
  yuborilmaydi (imzo pinned xabarda saqlangani uchun).

Eslatma: bot kanalda "Xabarlarni qadash" (Pin Messages) huquqiga ega bo'lsa,
indeks restart'lardan omon qoladi. Huquq bo'lmasa — faqat shu sessiyada ishlaydi.
"""

import json
import logging

from telegram import Bot

logger = logging.getLogger(__name__)

# Pinned indeks xabarining boshlang'ich belgisi (uni oddiy postlardan ajratish uchun)
MARKER = "AQLLI_RETSEPT_INDEX_V1"

# Pinned xabarda saqlanadigan imzolar soni cheklovi (Telegram 4096 belgi)
MAX_IMZO = 800


class ChannelService:
    """Retseptlarni kanalga dublikatsiz saqlovchi va imzolar indeksini yurituvchi servis."""

    def __init__(self, bot: Bot, channel_id: str) -> None:
        """Bot va kanal ID bilan servisni ishga tushiradi."""
        self._bot = bot
        self._channel_id = channel_id
        self._kesh: dict[str, dict] = {}   # sig -> to'liq retsept (shu sessiya uchun)
        self._imzolar: list[str] = []      # ma'lum imzolar (pinned xabarda saqlanadi)
        self._pin_id: int | None = None     # pinned indeks xabarining ID si

    # ──────────────────────────────────────────
    # Indeksni kanaldan yuklash / kanalga yozish
    # ──────────────────────────────────────────

    async def yukla(self) -> None:
        """Kanaldagi pinned indeks xabaridan ma'lum imzolarni yuklaydi (startda chaqiriladi)."""
        try:
            chat = await self._bot.get_chat(self._channel_id)
            pin = getattr(chat, "pinned_message", None)
            if pin and pin.text and pin.text.startswith(MARKER):
                malumot = json.loads(pin.text[len(MARKER):].strip())
                self._imzolar = malumot.get("imzolar", [])
                self._pin_id = pin.message_id
                logger.info("Kanal indeksi yuklandi: %d ta imzo", len(self._imzolar))
        except Exception as e:  # noqa: BLE001
            logger.error("Kanal indeksini yuklashda xato: %s", e)

    async def _pinni_yangila(self) -> None:
        """Ma'lum imzolar ro'yxatini pinned xabarda yangilaydi (yo'q bo'lsa yaratib qadaydi)."""
        try:
            imzolar = self._imzolar[-MAX_IMZO:]
            matn = (MARKER + "\n" + json.dumps({"imzolar": imzolar}, ensure_ascii=False))[:4090]
            if self._pin_id:
                await self._bot.edit_message_text(
                    chat_id=self._channel_id, message_id=self._pin_id, text=matn
                )
            else:
                xabar = await self._bot.send_message(chat_id=self._channel_id, text=matn)
                self._pin_id = xabar.message_id
                try:
                    await self._bot.pin_chat_message(
                        chat_id=self._channel_id,
                        message_id=self._pin_id,
                        disable_notification=True,
                    )
                except Exception as e:  # noqa: BLE001
                    logger.warning(
                        "Indeks xabarini qadab bo'lmadi (botga 'Pin Messages' huquqini "
                        "bering — aks holda restart'dan keyin dublikat bo'lishi mumkin): %s", e
                    )
        except Exception as e:  # noqa: BLE001
            logger.error("Pinned indeksni yangilashda xato: %s", e)

    # ──────────────────────────────────────────
    # Kesh va saqlash
    # ──────────────────────────────────────────

    def keshdan(self, sig: str) -> dict | None:
        """Shu sessiyada keshlangan retseptni imzo bo'yicha qaytaradi (bo'lmasa None)."""
        return self._kesh.get(sig)

    def bor(self, sig: str) -> bool:
        """Bu imzo bo'yicha retsept allaqachon kanalga yuborilganmi?"""
        return sig in self._imzolar

    async def saqla(self, retsept: dict, caption: str, rasm_url: str | None, sig: str) -> None:
        """Retseptni keshga qo'shadi va (faqat yangi bo'lsa) kanalga yuboradi.

        Imzo allaqachon ma'lum bo'lsa — kanalga qayta yuborilmaydi (dublikat oldi olinadi).
        """
        # Shu sessiya uchun keshga qo'yamiz (qayta ishlatish uchun)
        self._kesh[sig] = retsept

        if sig in self._imzolar:
            logger.info("Retsept allaqachon bazada — kanalga qayta yuborilmadi: %s",
                        retsept.get("taom"))
            return

        # Yangi retsept — kanalga joylaymiz
        try:
            if rasm_url:
                await self._bot.send_photo(
                    chat_id=self._channel_id, photo=rasm_url,
                    caption=caption[:1024], parse_mode="Markdown",
                )
            else:
                await self._bot.send_message(
                    chat_id=self._channel_id, text=caption[:4096], parse_mode="Markdown",
                )
            logger.info("Retsept kanalga saqlandi: %s", retsept.get("taom"))
        except Exception as e:  # noqa: BLE001
            logger.error("Kanalga saqlashda xato: %s", e)
            return  # yuborilmadi — imzoni ham qo'shmaymiz

        # Imzoni indeksga qo'shib, pinned xabarni yangilaymiz
        self._imzolar.append(sig)
        await self._pinni_yangila()
