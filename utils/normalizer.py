"""Masalliqlarni standart o'zbek nomlariga keltirish va hashtag yasash uchun yordamchilar.

Bu modul Claude API ga bog'liq bo'lmagan, tezkor (offline) normallashtirishni amalga oshiradi.
AI orqali to'liqroq normallashtirish `services.ai_service` ichida bajariladi.
"""

import re

# Ko'p uchraydigan variantlar -> standart o'zbek nomi
# Kalit: kichik harfli variant, qiymat: standart nom
SINONIMLAR: dict[str, str] = {
    # Tuxum
    "tuxumlar": "tuxum",
    "tuxum bor": "tuxum",
    "egg": "tuxum",
    "eggs": "tuxum",
    "яйцо": "tuxum",
    "яйца": "tuxum",
    # Kartoshka
    "kartoshkalar": "kartoshka",
    "potato": "kartoshka",
    "potatoes": "kartoshka",
    "картошка": "kartoshka",
    "картофель": "kartoshka",
    # Piyoz
    "piyozlar": "piyoz",
    "onion": "piyoz",
    "onions": "piyoz",
    "лук": "piyoz",
    # Sabzi
    "sabzilar": "sabzi",
    "carrot": "sabzi",
    "carrots": "sabzi",
    "морковь": "sabzi",
    # Go'sht
    "gosht": "go'sht",
    "meat": "go'sht",
    "мясо": "go'sht",
    "mol go'shti": "go'sht",
    # Yog'
    "yog": "yog'",
    "moy": "yog'",
    "oil": "yog'",
    "масло": "yog'",
    "o'simlik yog'i": "yog'",
    # Tuz
    "salt": "tuz",
    "соль": "tuz",
    # Pomidor
    "pomidorlar": "pomidor",
    "tomat": "pomidor",
    "tomato": "pomidor",
    "помидор": "pomidor",
    # Guruch
    "rice": "guruch",
    "рис": "guruch",
    # Un
    "flour": "un",
    "мука": "un",
    # Sut
    "milk": "sut",
    "молоко": "sut",
    # Sarimsoq
    "sarimsoqpiyoz": "sarimsoq",
    "garlic": "sarimsoq",
    "чеснок": "sarimsoq",
}


def matnni_bolaklarga_ajrat(matn: str) -> list[str]:
    """Foydalanuvchi yozgan erkin matnni alohida masalliqlarga ajratadi.

    Vergul, nuqta-vergul, yangi qator va "va" so'zi bo'yicha bo'linadi.
    """
    # "va" bog'lovchisini ham ajratuvchi sifatida qaraymiz
    qism = re.split(r"[,;\n]|(?:\sva\s)", matn)
    natija = [b.strip().strip(".").lower() for b in qism]
    return [b for b in natija if b]


def normallashtir(masalliqlar: list[str]) -> list[str]:
    """Masalliqlar ro'yxatini standart nomlarga keltiradi va takrorlarni olib tashlaydi.

    Bu offline (lug'atga asoslangan) normallashtirish — Claude chaqirilmaydi.
    """
    korilgan: set[str] = set()
    natija: list[str] = []
    for xom in masalliqlar:
        kichik = xom.strip().lower()
        standart = SINONIMLAR.get(kichik, kichik)
        if standart and standart not in korilgan:
            korilgan.add(standart)
            natija.append(standart)
    return natija


def hashtag_yasa(masalliqlar: list[str]) -> str:
    """Masalliqlar ro'yxatidan Telegram hashtaglar qatorini yasaydi.

    Masalan: ["tuxum", "kartoshka"] -> "#tuxum #kartoshka"
    Hashtag ichida bo'shliq va apostrof bo'lishi mumkin emas.
    """
    teglar = []
    for m in masalliqlar:
        tag = re.sub(r"[^\wа-яёА-ЯЎўҚқҒғҲҳ]", "", m.replace(" ", "_"))
        if tag:
            teglar.append(f"#{tag}")
    return " ".join(teglar)


def top_hashtaglar(masalliqlar: list[str], soni: int = 3) -> list[str]:
    """Kanal bazasidan qidirish uchun eng muhim (birinchi) N ta hashtagni qaytaradi."""
    teglar = hashtag_yasa(masalliqlar).split()
    return teglar[:soni]
