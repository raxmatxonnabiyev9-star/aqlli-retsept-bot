"""Groq API bilan ishlovchi servis (OpenAI-mos REST, httpx orqali).

Bu modul ilgari Gemini bilan ishlagan servisning Groq variantidir. Groq bepul
tieri ancha saxiy (kuniga minglab so'rov). Masalliqlarni normallashtirish, taom
variantlari, to'liq retsept va rasmdan masalliqlarni aniqlash uchun ishlatiladi.

Modellar:
  - Matn: llama-3.3-70b-versatile (JSON va o'zbek tilini yaxshi biladi)
  - Rasm: meta-llama/llama-4-scout-17b-16e-instruct (vision)

Interfeys avvalgidek (AIService klassi, AIXatosi) — handlerlar o'zgarmaydi.
"""

import asyncio
import json
import logging
import re

import httpx

logger = logging.getLogger(__name__)

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# Modellar
TEXT_MODEL = "llama-3.3-70b-versatile"
VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

# JSON parse xatosida nechi marta qayta urinish
MAX_URINISH = 2


class AIXatosi(Exception):
    """AI API (Groq) bilan ishlashda yuzaga kelgan umumiy xato."""


class AIService:
    """Groq API ga asinxron so'rovlar yuboruvchi servis."""

    def __init__(self, api_key: str) -> None:
        """Groq API kalitini saqlaydi."""
        self._api_key = api_key

    # ──────────────────────────────────────────
    # Ichki yordamchilar
    # ──────────────────────────────────────────

    @staticmethod
    def _json_ajrat(matn: str):
        """Javobdan birinchi JSON obyekti yoki massivni ajratib oladi."""
        tozalangan = re.sub(r"```(?:json)?", "", matn).strip()
        boshlanish = min(
            [i for i in (tozalangan.find("{"), tozalangan.find("[")) if i != -1],
            default=-1,
        )
        if boshlanish == -1:
            raise ValueError("Javobda JSON topilmadi")
        tugash = max(tozalangan.rfind("}"), tozalangan.rfind("]"))
        return json.loads(tozalangan[boshlanish : tugash + 1])

    async def _sorov(self, prompt: str, rasm_b64: str | None = None,
                     media_type: str = "image/jpeg"):
        """Groq ga so'rov yuborib, JSON natijani qaytaradi.

        Matn so'rovlarida JSON rejim (response_format) ishlatiladi; rasmli
        so'rovlarda vision model ishlatiladi. JSON parse xatosida MAX_URINISH
        marta qayta uradi; API/tarmoq xatosida AIXatosi ko'taradi.
        """
        # So'rov tanasini tayyorlaymiz
        if rasm_b64:
            body = {
                "model": VISION_MODEL,
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url",
                         "image_url": {"url": f"data:{media_type};base64,{rasm_b64}"}},
                    ],
                }],
                "temperature": 0.5,
            }
        else:
            body = {
                "model": TEXT_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"},
                "temperature": 0.7,
            }

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        oxirgi_xato: Exception | None = None
        for urinish in range(1, MAX_URINISH + 1):
            try:
                async with httpx.AsyncClient(timeout=45.0) as client:
                    javob = await client.post(GROQ_URL, headers=headers, json=body)
                    javob.raise_for_status()
                    matn = javob.json()["choices"][0]["message"]["content"]
                return self._json_ajrat(matn)
            except (json.JSONDecodeError, ValueError, KeyError) as e:
                # JSON noto'g'ri — qayta urinamiz
                oxirgi_xato = e
                logger.warning("JSON parse xatosi (%d-urinish): %s", urinish, e)
                continue
            except Exception as e:  # noqa: BLE001 — API/tarmoq xatolari
                logger.error("Groq API xatosi: %s", e)
                raise AIXatosi(str(e)) from e

        logger.error("JSON parse barcha urinishlarda muvaffaqiyatsiz: %s", oxirgi_xato)
        raise AIXatosi("Javobni o'qib bo'lmadi")

    # ──────────────────────────────────────────
    # Ommaviy metodlar (handlerlar shu nomlar bilan chaqiradi)
    # ──────────────────────────────────────────

    async def normallashtir(self, user_input: str) -> list[str]:
        """Masalliqlarni standart o'zbek nomlariga keltiradi (JSON massiv)."""
        prompt = (
            "Siz masalliqlarni normallashtiruvchi yordamchisiz. Quyidagi masalliqlar "
            "ro'yxatini o'zbek tilida standart nomlarga o'tkazing.\n"
            "Faqat JSON qaytaring: {\"masalliqlar\": [\"tuxum\", \"kartoshka\", \"piyoz\"]}\n\n"
            f"Masalliqlar: {user_input}"
        )
        natija = await self._sorov(prompt)
        ro = natija.get("masalliqlar", natija) if isinstance(natija, dict) else natija
        if not isinstance(ro, list):
            raise AIXatosi("Normallashtirish natijasi massiv emas")
        return [str(x).strip() for x in ro if str(x).strip()]

    async def variantlar(self, masalliqlar: list[str]) -> list[dict]:
        """Berilgan masalliqlardan 3 ta turli taom taklif qiladi."""
        masalliqlar_str = ", ".join(masalliqlar)
        prompt = (
            "Siz professional o'zbek oshpazisiz.\n"
            f"Foydalanuvchida FAQAT quyidagi masalliqlar bor: {masalliqlar_str}\n\n"
            "Faqat shu masalliqlardan tayyorlanishi mumkin bo'lgan 3 ta TURLI taom taklif qil.\n"
            "Taomlar xilma-xil bo'lsin: o'zbek, yevropa, osiyo oshxonalaridan.\n\n"
            "Faqat JSON qaytar:\n"
            '{"taomlar": [{"nom": "Qovurma kartoshka", "oshxona": "O\'zbek", '
            '"vaqt_daqiqa": 20, "qiyinlik": "Oson"}]}'
        )
        natija = await self._sorov(prompt)
        return natija.get("taomlar", []) if isinstance(natija, dict) else []

    async def toliq_retsept(self, taom_nomi: str, masalliqlar: list[str]) -> dict:
        """Tanlangan taom uchun to'liq retseptni qaytaradi."""
        masalliqlar_str = ", ".join(masalliqlar)
        prompt = (
            "Siz professional oshpazsiz. Quyidagi taomni pishirishni to'liq tushuntiring.\n"
            f"Taom: {taom_nomi}\n"
            f"Foydalanuvchida bor masalliqlar: {masalliqlar_str}\n\n"
            "Faqat JSON qaytaring (barcha matnlar o'zbek tilida):\n"
            '{\n'
            f'  "taom": "{taom_nomi}",\n'
            '  "oshxona": "O\'zbek", "vaqt_daqiqa": 25, "qiyinlik": "Oson",\n'
            '  "porsiya": "2 kishi uchun",\n'
            '  "masalliqlar": [{"nom": "Kartoshka", "miqdor": "3 ta"}],\n'
            '  "bosqichlar": [{"raqam": 1, "sarlavha": "...", "tavsif": "...", '
            '"maslahat": "...", "vaqt_daqiqa": 5}],\n'
            '  "oshpaz_maslahatlari": ["..."],\n'
            '  "kaloriya": 320, "oqsil": "12g", "uglerod": "38g", "yog_miqdori": "14g",\n'
            '  "hashtag": "#qovurma #kartoshka #uzbek"\n'
            '}'
        )
        natija = await self._sorov(prompt, )
        if not isinstance(natija, dict):
            raise AIXatosi("Retsept natijasi obyekt emas")
        return natija

    async def rasmdan_masalliqlar(self, rasm_b64: str, media_type: str = "image/jpeg") -> list[str]:
        """Yuborilgan rasmdan (muzlatgich tarkibi) masalliqlarni aniqlaydi."""
        prompt = (
            "Rasmda ko'rinayotgan barcha oziq-ovqat mahsulotlarini aniqlang.\n"
            "Faqat o'zbek tilida JSON qaytaring, boshqa hech narsa yozmang:\n"
            '{"masalliqlar": ["go\'sht", "sabzi", "kartoshka", "piyoz"]}'
        )
        natija = await self._sorov(prompt, rasm_b64=rasm_b64, media_type=media_type)
        ro = natija.get("masalliqlar", natija) if isinstance(natija, dict) else natija
        if not isinstance(ro, list):
            raise AIXatosi("Rasm tahlili natijasi massiv emas")
        return [str(x).strip() for x in ro if str(x).strip()]
