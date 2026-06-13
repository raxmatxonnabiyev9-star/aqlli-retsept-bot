"""Mini App uchun retseptlarni vaqtincha saqlovchi oddiy xotira ombori.

Bot retsept yaratganda uni shu yerga saqlaydi va qisqa ID oladi. Mini App
(web sahifa) shu ID bo'yicha `/api/recipe/<id>` orqali retseptni so'raydi.

Eslatma: bu jarayon xotirasidagi oddiy dict — bot qayta ishga tushsa tozalanadi.
Kichik bot uchun yetarli; doimiy saqlash kerak bo'lsa kanal bazasi ishlatiladi.
"""

import uuid

# Oxirgi N ta retsept xotirada saqlanadi (xotira cheksiz o'smasligi uchun)
MAX_RETSEPT = 500

_STORE: dict[str, dict] = {}
_TARTIB: list[str] = []


def saqla(retsept: dict) -> str:
    """Retseptni saqlaydi va unga qisqa noyob ID qaytaradi."""
    rid = uuid.uuid4().hex[:12]
    _STORE[rid] = retsept
    _TARTIB.append(rid)
    # Eski yozuvlarni tozalaymiz
    while len(_TARTIB) > MAX_RETSEPT:
        eski = _TARTIB.pop(0)
        _STORE.pop(eski, None)
    return rid


def ol(rid: str) -> dict | None:
    """ID bo'yicha retseptni qaytaradi (topilmasa None)."""
    return _STORE.get(rid)
