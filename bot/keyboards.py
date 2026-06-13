"""Inline keyboard (ichki tugmalar) yasovchi funksiyalar."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

# Oshxona turiga qarab emoji tanlash uchun jadval
_OSHXONA_EMOJI: dict[str, str] = {
    "o'zbek": "🍳",
    "ozbek": "🍳",
    "yevropa": "🍝",
    "osiyo": "🥢",
    "italyan": "🍝",
    "rus": "🥘",
}


def _taom_emoji(taom: dict) -> str:
    """Taom oshxonasiga mos emoji qaytaradi (topilmasa standart emoji)."""
    oshxona = (taom.get("oshxona", "") or "").lower()
    return _OSHXONA_EMOJI.get(oshxona, "🍴")


def variantlar_klaviaturasi(taomlar: list[dict]) -> InlineKeyboardMarkup:
    """3 ta (yoki kamroq) taom varianti uchun tugmalar yasaydi.

    Har bir tugma callback_data si "recipe_<index>" ko'rinishida bo'ladi.
    Oxirida "🔄 Boshqa variantlar" tugmasi qo'shiladi.
    """
    tugmalar: list[list[InlineKeyboardButton]] = []
    for i, taom in enumerate(taomlar):
        emoji = _taom_emoji(taom)
        nom = taom.get("nom", "Taom")
        vaqt = taom.get("vaqt_daqiqa", "?")
        matn = f"{emoji} {nom} ({vaqt} min)"
        tugmalar.append(
            [InlineKeyboardButton(matn, callback_data=f"recipe_{i}")]
        )
    tugmalar.append(
        [InlineKeyboardButton("🔄 Boshqa variantlar", callback_data="more_variants")]
    )
    return InlineKeyboardMarkup(tugmalar)


def retsept_klaviaturasi() -> InlineKeyboardMarkup:
    """To'liq retsept ko'rsatilgandan keyingi tugmalar (boshqa taom / sevimlilar)."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🔄 Boshqa taom", callback_data="restart"),
                InlineKeyboardButton("❤️ Sevimlilar", callback_data="favorite"),
            ]
        ]
    )


def miniapp_klaviaturasi(url: str) -> InlineKeyboardMarkup:
    """Mini App'ni (retsept kartasi) ochuvchi tugma + boshqa taom/sevimlilar.

    `url` — https manzil bo'lishi shart (Telegram Mini App talabi).
    """
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📖 Retseptni ochish", web_app=WebAppInfo(url=url))],
            [
                InlineKeyboardButton("🔄 Boshqa taom", callback_data="restart"),
                InlineKeyboardButton("❤️ Sevimlilar", callback_data="favorite"),
            ],
        ]
    )
