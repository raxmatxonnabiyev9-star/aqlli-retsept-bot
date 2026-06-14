"""Google Gemini API bilan ishlovchi servis.

Bu modul ilgari Claude API bilan ishlagan servisning Gemini variantidir.
Masalliqlarni normallashtirish, taom variantlari taklif qilish, to'liq retsept
olish va rasmdan masalliqlarni aniqlash uchun Gemini API ga (gemini-1.5-flash)
asinxron so'rov yuboradi.

Eslatma: Gemini SDK sinxron (bloklovchi) ishlaydi, shuning uchun har bir so'rov
`asyncio.to_thread` orqali alohida thread'da bajariladi — bu event loop'ni
bloklamaydi va bot bir vaqtda ko'p foydalanuvchiga xizmat qila oladi.
"""

import asyncio
import base64
import io
import json
import logging
import re

import google.generativeai as genai
import PIL.Image

logger = logging.getLogger(__name__)

# Tezkor, bepul va rasm tahlil qila oladigan model.
# Eslatma: gemini-2.5-flash ning bepul kunlik limiti juda kichik (20 so'rov/kun),
# shuning uchun bepul kunlik limiti kattaroq bo'lgan gemini-2.0-flash ishlatiladi.
MODEL = "gemini-2.0-flash"

# JSON parse xatosida nechi marta qayta urinish
MAX_URINISH = 2


class AIXatosi(Exception):
    """AI API (Gemini) bilan ishlashda yuzaga kelgan umumiy xato."""


class AIService:
    """Gemini API ga asinxron so'rovlar yuboruvchi servis."""

    def __init__(self, api_key: str) -> None:
        """Gemini API kalitini sozlaydi va gemini-1.5-flash modelini tayyorlaydi."""
        genai.configure(api_key=api_key)
        self._model = genai.GenerativeModel(MODEL)

    # ──────────────────────────────────────────
    # Ichki yordamchilar
    # ──────────────────────────────────────────

    @staticmethod
    def _json_ajrat(matn: str):
        """Gemini javobidan birinchi JSON obyekti yoki massivni ajratib oladi.

        Gemini ba'zan JSON atrofida ```json ``` bloklar yoki qo'shimcha matn
        qaytarishi mumkin — shu sababli ehtiyotkorlik bilan tozalab ajratamiz.
        """
        tozalangan = matn.strip().replace("```json", "").replace("```", "").strip()
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
        """Gemini ga so'rov yuborib, JSON natijani qaytaradi.

        JSON parse muvaffaqiyatsiz bo'lsa, MAX_URINISH marta qayta uradi.
        Tarmoq yoki API xatosida AIXatosi ko'taradi. Gemini bloklovchi bo'lgani
        uchun so'rov `asyncio.to_thread` orqali bajariladi.
        """
        oxirgi_xato: Exception | None = None
        for urinish in range(1, MAX_URINISH + 1):
            try:
                if rasm_b64:
                    # base64 -> bayt -> PIL rasm
                    rasm_bytes = base64.b64decode(rasm_b64)
                    rasm = PIL.Image.open(io.BytesIO(rasm_bytes))
                    javob = await asyncio.to_thread(
                        self._model.generate_content, [prompt, rasm]
                    )
                else:
                    javob = await asyncio.to_thread(
                        self._model.generate_content, prompt
                    )
                return self._json_ajrat(javob.text)
            except (json.JSONDecodeError, ValueError) as e:
                # JSON noto'g'ri — qayta urinamiz
                oxirgi_xato = e
                logger.warning("JSON parse xatosi (%d-urinish): %s", urinish, e)
                continue
            except Exception as e:  # noqa: BLE001 — API/tarmoq xatolari
                logger.error("Gemini API xatosi: %s", e)
                raise AIXatosi(str(e)) from e

        logger.error("JSON parse barcha urinishlarda muvaffaqiyatsiz: %s", oxirgi_xato)
        raise AIXatosi("Javobni o'qib bo'lmadi")

    # ──────────────────────────────────────────
    # Ommaviy metodlar (handlerlar shu nomlar bilan chaqiradi)
    # ──────────────────────────────────────────

    async def normallashtir(self, user_input: str) -> list[str]:
        """Foydalanuvchi yozgan masalliqlarni standart o'zbek nomlariga keltiradi.

        Misol: "tuxumlar, egg, kartoshka bor" -> ["tuxum", "kartoshka"]
        Gemini faqat JSON massiv qaytaradi.
        """
        prompt = (
            "Siz masalliqlarni normallashtiruvchi yordamchisiz.\n"
            "Quyidagi masalliqlar ro'yxatini o'zbek tilida standart nomlarga o'tkazing.\n"
            "Faqat JSON array qaytaring, boshqa hech narsa yozmang.\n"
            'Misol: ["tuxum", "kartoshka", "piyoz"]\n\n'
            f"Masalliqlar: {user_input}"
        )
        natija = await self._sorov(prompt)
        if not isinstance(natija, list):
            raise AIXatosi("Normallashtirish natijasi massiv emas")
        return [str(x).strip() for x in natija if str(x).strip()]

    async def variantlar(self, masalliqlar: list[str]) -> list[dict]:
        """Berilgan masalliqlardan tayyorlanishi mumkin 3 ta turli taom taklif qiladi."""
        masalliqlar_str = ", ".join(masalliqlar)
        prompt = (
            "Siz professional oshpazsiz.\n"
            f"Foydalanuvchida FAQAT quyidagi masalliqlar bor: {masalliqlar_str}\n\n"
            "Faqat shu masalliqlardan tayyorlanishi mumkin bo'lgan 3 ta TURLI taom taklif qil.\n"
            "Taomlar xilma-xil bo'lsin: o'zbek, yevropa, osiyo oshxonalaridan.\n\n"
            "Faqat JSON qaytar, boshqa hech narsa yozma:\n"
            '{\n'
            '  "taomlar": [\n'
            '    {\n'
            '      "nom": "Qovurma kartoshka",\n'
            '      "oshxona": "O\'zbek",\n'
            '      "vaqt_daqiqa": 20,\n'
            '      "qiyinlik": "Oson",\n'
            '      "emoji": "🍳"\n'
            '    }\n'
            '  ]\n'
            '}'
        )
        natija = await self._sorov(prompt)
        taomlar = natija.get("taomlar", []) if isinstance(natija, dict) else []
        return taomlar

    async def toliq_retsept(self, taom_nomi: str, masalliqlar: list[str]) -> dict:
        """Tanlangan taom uchun to'liq retseptni (bosqichlar, maslahatlar, kaloriya) qaytaradi."""
        masalliqlar_str = ", ".join(masalliqlar)
        prompt = (
            "Siz professional oshpazsiz.\n"
            f"Taom: {taom_nomi}\n"
            f"Foydalanuvchida bor masalliqlar: {masalliqlar_str}\n\n"
            "Faqat JSON qaytaring, boshqa hech narsa yozmang:\n"
            '{\n'
            f'  "taom": "{taom_nomi}",\n'
            '  "oshxona": "O\'zbek",\n'
            '  "vaqt_daqiqa": 25,\n'
            '  "qiyinlik": "Oson",\n'
            '  "porsiya": "2 kishi uchun",\n'
            '  "masalliqlar": [{"nom": "Kartoshka", "miqdor": "3 ta (o\'rta)"}],\n'
            '  "bosqichlar": [{"raqam": 1, "sarlavha": "...", "tavsif": "...", '
            '"maslahat": "...", "vaqt_daqiqa": 5}],\n'
            '  "oshpaz_maslahatlari": ["..."],\n'
            '  "kaloriya": 320,\n'
            '  "oqsil": "12g",\n'
            '  "uglerod": "38g",\n'
            '  "yog_miqdori": "14g",\n'
            '  "hashtag": "#qovurma #kartoshka #uzbek"\n'
            '}'
        )
        natija = await self._sorov(prompt)
        if not isinstance(natija, dict):
            raise AIXatosi("Retsept natijasi obyekt emas")
        return natija

    async def rasmdan_masalliqlar(self, rasm_b64: str, media_type: str = "image/jpeg") -> list[str]:
        """Yuborilgan rasmdan (muzlatgich tarkibi) ko'rinayotgan masalliqlarni aniqlaydi."""
        prompt = (
            "Siz muzlatgich tarkibini aniqlovchi yordamchisiz.\n"
            "Rasmda ko'rinayotgan barcha oziq-ovqat mahsulotlarini aniqlang.\n"
            "Faqat o'zbek tilida JSON array qaytaring, boshqa hech narsa yozmang.\n"
            'Misol: ["go\'sht", "sabzi", "kartoshka", "piyoz"]'
        )
        natija = await self._sorov(prompt, rasm_b64=rasm_b64, media_type=media_type)
        if not isinstance(natija, list):
            raise AIXatosi("Rasm tahlili natijasi massiv emas")
        return [str(x).strip() for x in natija if str(x).strip()]
