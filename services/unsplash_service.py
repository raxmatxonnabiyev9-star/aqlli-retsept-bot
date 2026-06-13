"""Unsplash API orqali taom rasmlarini olish servisi (asinxron, httpx asosida)."""

import logging

import httpx

logger = logging.getLogger(__name__)

UNSPLASH_URL = "https://api.unsplash.com/search/photos"


class UnsplashService:
    """Unsplash dan ovqat rasmlari URL manzilini oluvchi servis."""

    def __init__(self, access_key: str) -> None:
        """Unsplash access key bilan servisni ishga tushiradi."""
        self._access_key = access_key

    async def taom_rasmi(self, taom_nomi: str) -> str | None:
        """Berilgan taom nomi bo'yicha bitta rasm URL manzilini qaytaradi.

        Rasm topilmasa yoki xato bo'lsa None qaytaradi (bot default emoji ishlatadi).
        Qidiruvga "food" so'zi qo'shiladi — ovqat rasmlari chiqishi ehtimolini oshirish uchun.
        """
        if not self._access_key:
            logger.warning("UNSPLASH_ACCESS_KEY o'rnatilmagan — rasm yuborilmaydi")
            return None

        params = {
            "query": f"{taom_nomi} food dish",
            "per_page": 1,
            "orientation": "landscape",
        }
        headers = {"Authorization": f"Client-ID {self._access_key}"}

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                javob = await client.get(UNSPLASH_URL, params=params, headers=headers)
                javob.raise_for_status()
                malumot = javob.json()
                natijalar = malumot.get("results", [])
                if not natijalar:
                    logger.info("Unsplash: '%s' uchun rasm topilmadi", taom_nomi)
                    return None
                return natijalar[0]["urls"]["regular"]
        except Exception as e:  # noqa: BLE001 — har qanday tarmoq/parse xatosi
            logger.error("Unsplash xatosi: %s", e)
            return None
