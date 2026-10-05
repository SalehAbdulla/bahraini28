"""Seed the 28 elite-card partner businesses together with their logos.

Sources (both kept out of git history; see the ``data/`` directory):

* ``elite card.xlsx`` — the volunteer-discount sheet: project name, Instagram
  handle and the benefit each partner grants Bahraini 28 volunteers.
* ``PS A3.pdf`` — the A3 poster deck, one page per partner. The deck order is
  **not** the sheet order, so every logo in ``assets/business_logos/`` was
  matched to its partner by the artwork on that page (the page each partner was
  found on is recorded inline in ``PARTNERS``, which itself follows the sheet).

Usage (from the backend/ directory):
    cd backend
    PYTHONPATH=. ../.venv/bin/python scripts/seed_partners.py

Idempotent in the same style as ``scripts/seed.py``: a partner is matched on its
name, an existing row is left untouched (an edit made in the admin UI always
wins), and a logo is attached only while the partner still has no
``logo_path``. The logo PNGs live next to this script — ``backend/scripts`` is
copied into the production image — so the same command works on the server:

    docker compose -f deploy/docker-compose.yml run --rm backend \
        python scripts/seed_partners.py

Two fields the sheet does not carry are placeholders until an admin fills them:
the commercial-registration number (registered as ``PENDING-<slug>``) and the
branch list (left empty). Category placement, by contrast, is a first-pass
reading of each partner's artwork and offer text; the admin UI is the place to
correct it.
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models import Business, Category

#: One PNG per partner slug, extracted from the poster deck (rendered with
#: Ghostscript, cropped, trimmed of its page margin and capped at 512 px).
LOGO_DIR = Path(__file__).resolve().parent / "assets" / "business_logos"

#: Categories the partner set needs. The first five match ``scripts/seed.py``;
#: ``services`` is added here for the laundry, the tailor and the garden.
CATEGORIES: list[tuple[str, str]] = [
    ("Restaurants & Cafes", "restaurants"),
    ("Health & Beauty", "health-beauty"),
    ("Retail & Shopping", "retail"),
    ("Education & Books", "education"),
    ("Sports & Fitness", "sports-fitness"),
    ("Services", "services"),
]


@dataclass(frozen=True)
class Partner:
    """One elite-card row paired with the logo drawn for it in the deck."""

    #: Logo file name (without extension) and the tail of the CR placeholder.
    slug: str
    #: Commercial name shown in the directory. The brand's own typography wins
    #: where it differs from the sheet (``mq`` -> ``MQ``, ``unocafebh`` ->
    #: ``Uno Cafe``) and the one typo on the sheet is corrected
    #: (``أعشاب روح الطيبيعة`` -> ``أعشاب روح الطبيعة``, as the logo prints it).
    name: str
    #: Category slug declared in ``CATEGORIES``.
    category: str
    #: Whole-number discount shown in the directory badge. ``0`` means the
    #: benefit is not a flat percentage — ``offer`` spells out what it is.
    discount: int
    #: The volunteer benefit as advertised on the elite card (Arabic digits
    #: normalised to Western ones, which is what the badge and admin UI use).
    offer: str
    #: Instagram handle from the sheet, kept for provenance.
    handle: str | None = None
    #: Poster-deck page the logo was taken from (0-based).
    page: int = 0


#: The 28 partners, in elite-card row order.
PARTNERS: list[Partner] = [
    # --- 1-5: abayas, fragrance, tailoring, kitchen flame, skincare ---
    Partner("orya-abaya", "عبايات أوريا", "retail", 15, "خصم 15%", "orya_abaya", 2),
    Partner("manso", "مانسو", "retail", 10, "خصم 10%", "manso.bh", 0),
    Partner("mudhafar-perfume", "مظفر للعطور", "health-beauty", 20, "خصم 20%", "mudhafar_perfume", 1),
    Partner("alola-tailoring", "العلا", "services", 0, "Special offer", "alola.tailoring", 3),
    Partner("lahab", "لهب", "retail", 20, "خصم 20%", "lahab.bh", 4),
    # --- 6-10: skincare, supplements, jewellery, watches, hospital ---
    Partner("by-perla", "By Perla", "health-beauty", 20, "خصم 20%", "byperlacare.bh", 5),
    Partner("master-muscles", "ماستر مسلز", "sports-fitness", 15, "خصم 15%", "master_muscles", 6),
    Partner("lamar-jewellery", "مجوهرات لمار", "retail", 0, "سعر خاص", "lamarjewellery_bh", 7),
    Partner("b7watches", "B7watches", "retail", 25, "خصم 25%", "b7watches", 8),
    Partner("alhilal-premier", "مستشفى الهلال", "health-beauty", 0, "خدمات مختارة", "alhilalpremierhospital", 9),
    # --- 11-16: flowers, bookstore, car accessories, sweets, coffee, dessert ---
    Partner("julian-flowers", "جوليان فلورز", "retail", 10, "خصم 10%", "julian.flowers.bh", 10),
    Partner("dar-shaghaf", "مكتبة شغف", "education", 15, "خصم 15%", "darshghf_bh", 11),
    Partner(
        "mq-cars",
        "MQ",
        "retail",
        10,
        "خصم 10% على الديمات والكشافات / الباليسات والملمعات خصم من 5 إلى 10% / "
        "تفصيل ستيكرات بسعر خاص / سماعات وسستم 5% / تخفيض شاشات 5%",
        "mq cars",
        12,
    ),
    Partner(
        "icreamplus",
        "iCream Plus",
        "restaurants",
        25,
        "خصم 25% على أي أوردر فوق 25 دينار / 20% على الكيك الحجم الصغير + كمية صغيرة",
        "icreamplus",
        13,
    ),
    Partner("brew-rista", "Brew Rista", "restaurants", 20, "خصم 20% للفردي / 28% للدائم + الورش", "brewrista.bh", 14),
    Partner("nice-mood", "Nice Mood", "restaurants", 30, "خصم يصل إلى 30%", "nice.mood.bh", 15),
    # --- 17-21: wellness, herbal, eyewear, laundry, beauty ---
    Partner("vitalia", "فيتاليا", "health-beauty", 0, "أسعار خاصة", page=16),
    Partner("spirit-of-nature", "أعشاب روح الطبيعة", "health-beauty", 20, "خصم 20% / أسعار خاصة", "spirit_of_nature91", 17),
    Partner(
        "ammar-optics",
        "نظارات عمار",
        "health-beauty",
        50,
        "خصم 50% على النظارات الشمسية والإطارات الطبية / خصم حتى 25% على العدسات "
        "البلاستيك والزجاج / فحص النظر مجاناً كل 6 أشهر / خصم 5% إضافي على النظارات "
        "الشمسية والإطارات الطبية في حال وجود خصومات أخرى",
        page=18,
    ),
    Partner("bravo-laundry", "مغسلة برافوا", "services", 20, "خصم 20% على الفاتورة / جميع الفروع", "bravo.laundry_", 19),
    Partner("beautiqo", "بيوتيكو", "health-beauty", 15, "خصم 15% على الفاتورة", "beautiqobh", 20),
    # --- 22-28: ice cream, shoes, garden, fashion, gym, cafe, flowers ---
    Partner("frozo", "Frozo", "restaurants", 0, "آيس كريم مجاني بعدد يتفق عليه كل أسبوع", "frozo_bh", 23),
    Partner("catchy-step", "أحذية الخطوة الملفتة", "retail", 0, "نسبة ربح مقابل كل عملية بيع حذاء", "catchy__step", 24),
    Partner("yasmin-garden", "حدائق ياسمين", "services", 10, "خصم 10% لحاملي البطاقة / 6 مرات دخول مجاني في السنة", "yasmingarden86", 21),
    Partner("ali-moda", "علي مودا", "retail", 0, "أسعار خاصة", "ali_moda20", 22),
    Partner("the-gym", "الجيم", "sports-fitness", 0, "10 days extra on the month", page=25),
    Partner("unocafe", "Uno Cafe", "restaurants", 0, "Special offer", "unocafebh", 26),
    Partner("enaaq-flowers", "عناق للورد", "retail", 20, "خصم 20%", "enaaq.flowers", 27),
]


def _tznow(days: int = 0) -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=days)


def _ensure_categories(db: Session) -> dict[str, Category]:
    """Get-or-create the categories in ``CATEGORIES``, keyed by slug."""
    cats: dict[str, Category] = {}
    for name, slug in CATEGORIES:
        category = db.scalar(select(Category).where(Category.slug == slug))
        if category is None:
            category = Category(name=name, slug=slug, description=f"{name} partners")
            db.add(category)
            db.flush()
        cats[slug] = category
    return cats


def _attach_logo(business: Business, partner: Partner, upload_dir: Path) -> bool:
    """Copy the bundled logo into ``upload_dir`` and point ``logo_path`` at it.

    Returns False when the PNG is missing so the caller can report it instead of
    writing a dangling ``logo_path`` (the SPA falls back to the name initial).
    """
    source = LOGO_DIR / f"{partner.slug}.png"
    if not source.exists():
        return False
    node = f"partner-{partner.slug}.png"
    shutil.copyfile(source, upload_dir / node)
    business.logo_path = f"/uploads/{node}"
    return True


def seed() -> None:
    settings = get_settings()
    Base.metadata.create_all(bind=engine)

    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)

    created: list[Partner] = []
    already_present: list[str] = []
    logos_written = 0
    missing_logos: list[str] = []

    with SessionLocal() as db:
        cats = _ensure_categories(db)
        for partner in PARTNERS:
            business = db.scalar(select(Business).where(Business.name == partner.name))
            if business is None:
                business = Business(
                    name=partner.name,
                    # The sheet carries no CR, so the row starts on a clearly
                    # fake value for an admin to replace.
                    commercial_registration=f"PENDING-{partner.slug}",
                    category_id=cats[partner.category].id,
                    discount_percentage=partner.discount,
                    description=partner.offer,
                    is_active=True,
                    expiry_date=_tznow(365),
                )
                db.add(business)
                db.flush()
                created.append(partner)
            else:
                already_present.append(partner.name)

            # A logo already on file belongs to an admin edit — leave it alone.
            if business.logo_path:
                continue
            if _attach_logo(business, partner, upload_dir):
                logos_written += 1
            else:
                missing_logos.append(partner.slug)
        db.commit()
        # Materialised while the session is still open, so the summary printed
        # below only ever reads plain tuples and not ORM attributes.
        created_summary = [(p.name, p.discount, p.category, p.handle) for p in created]

    print(
        f"Partners: {len(created_summary)} created, {len(already_present)} already "
        f"present ({len(PARTNERS)} on the elite card)."
    )
    print(f"Logos   : {logos_written} written to {upload_dir}")
    if missing_logos:
        print(f"          missing PNG(s): {', '.join(missing_logos)}")
    if created_summary:
        print("New partners (benefit / category / handle):")
        for name, discount, category, handle in created_summary:
            benefit = f"-{discount}%" if discount else "special offer"
            print(f"  {name}  ·  {benefit}  ·  {category}  ·  @{handle or '—'}")
    print("Still to fill in from the admin UI:")
    print("  - commercial registration (every row starts as PENDING-<slug>)")
    print("  - branches/areas (the elite card lists no addresses)")


if __name__ == "__main__":
    seed()
