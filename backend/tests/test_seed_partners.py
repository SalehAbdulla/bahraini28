"""Coverage for ``scripts/seed_partners.py`` — the elite-card partner seed.

That script is the only thing that puts the 28 pilot partners, their logos and
their volunteer discounts into a database, and it is data-driven: a typo in the
``PARTNERS`` table would ship silently as a partner without a logo, a category
slug that does not exist, or two partners sharing one deck page. So these tests
first pin the table itself — it has to stay in step with the logo files sitting
next to the script — and then run the real ``seed()`` twice against a throwaway
SQLite database and upload directory. The second run must create nothing and
rewrite no logo, which is what makes the script safe to re-run on the production
database during a pilot update.
"""
from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app.db.base import Base
from app.db.session import create_session_factory
from app.models import Business, Category
from scripts import seed_partners
from tests.conftest import make_test_settings

PARTNER_SLUGS = {partner.slug for partner in seed_partners.PARTNERS}
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


@pytest.fixture
def seeded(tmp_path, monkeypatch):
    """Point the seed at a throwaway database and upload directory."""
    engine, session_local = create_session_factory(make_test_settings())
    settings = make_test_settings().model_copy(
        update={"UPLOAD_DIR": str(tmp_path / "uploads")}
    )
    monkeypatch.setattr(seed_partners, "engine", engine)
    monkeypatch.setattr(seed_partners, "SessionLocal", session_local)
    monkeypatch.setattr(seed_partners, "get_settings", lambda: settings)
    yield session_local, tmp_path / "uploads"
    # Drop what the seed created: with TEST_DATABASE_URL set (CI's PostgreSQL
    # job) every test shares one database, exactly like the ``db`` fixture.
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


# --- the data table itself -----------------------------------------------------


def test_table_holds_one_row_per_deck_page():
    """28 partners, one poster-deck page each: no gaps, no double-mapping."""
    assert len(seed_partners.PARTNERS) == 28
    assert sorted(p.page for p in seed_partners.PARTNERS) == list(range(28))
    # The name is the idempotency key, the slug the logo + CR placeholder.
    assert len({p.name for p in seed_partners.PARTNERS}) == 28
    assert len(PARTNER_SLUGS) == 28


def test_every_row_fits_the_business_columns():
    """Values must satisfy the model's column widths and the API schema."""
    categories = {slug for _, slug in seed_partners.CATEGORIES}
    for partner in seed_partners.PARTNERS:
        assert partner.category in categories, partner.slug
        assert 0 <= partner.discount <= 100, partner.slug  # AdminBusinessCreate
        assert partner.offer.strip(), partner.slug  # becomes `description`
        assert len(partner.name) <= 160, partner.slug  # businesses.name
        assert len(f"PENDING-{partner.slug}") <= 60, partner.slug  # businesses.cr


def test_logo_files_match_the_table():
    """Every partner has exactly one intact PNG, and nothing is orphaned."""
    for partner in seed_partners.PARTNERS:
        path = seed_partners.LOGO_DIR / f"{partner.slug}.png"
        assert path.exists(), partner.slug
        assert path.read_bytes()[:8] == PNG_MAGIC, partner.slug
    on_disk = {path.stem for path in seed_partners.LOGO_DIR.glob("*.png")}
    assert on_disk == PARTNER_SLUGS


# --- running it ----------------------------------------------------------------


def test_seed_creates_each_partner_with_its_logo(seeded):
    session_local, upload_dir = seeded
    seed_partners.seed()

    with session_local() as db:
        categories = {c.id: c.slug for c in db.scalars(select(Category)).all()}
        businesses = {b.name: b for b in db.scalars(select(Business)).all()}
        assert db.scalar(select(func.count(Business.id))) == len(seed_partners.PARTNERS)
        # The one category the demo seed does not already provide.
        assert "services" in set(categories.values())

        for partner in seed_partners.PARTNERS:
            business = businesses[partner.name]
            assert business.logo_path == f"/uploads/partner-{partner.slug}.png"
            assert business.discount_percentage == partner.discount
            assert business.description == partner.offer
            assert business.commercial_registration == f"PENDING-{partner.slug}"
            assert categories[business.category_id] == partner.category
            assert business.is_active is True
            assert business.expiry_date > business.created_at

    # The copy is byte-for-byte the bundled asset, so /uploads serves the poster
    # artwork itself and not a re-encoded thumbnail.
    for partner in seed_partners.PARTNERS:
        copied = upload_dir / f"partner-{partner.slug}.png"
        original = seed_partners.LOGO_DIR / f"{partner.slug}.png"
        assert copied.read_bytes() == original.read_bytes(), partner.slug


def test_reseeding_creates_nothing_and_keeps_an_admin_logo(seeded, capsys):
    """A logo replaced in the admin UI must survive a later seed run."""
    session_local, upload_dir = seeded
    partner = seed_partners.PARTNERS[0]
    seed_partners.seed()
    capsys.readouterr()

    replaced = upload_dir / "admin-replaced.png"
    replaced.write_bytes(b"<admin upload>")
    with session_local() as db:
        business = db.scalar(select(Business).where(Business.name == partner.name))
        business.logo_path = "/uploads/admin-replaced.png"
        db.commit()

    seed_partners.seed()
    output = capsys.readouterr().out

    assert f"0 created, {len(seed_partners.PARTNERS)} already present" in output
    assert "Logos   : 0 written" in output
    with session_local() as db:
        assert db.scalar(select(func.count(Business.id))) == len(seed_partners.PARTNERS)
        business = db.scalar(select(Business).where(Business.name == partner.name))
        assert business.logo_path == "/uploads/admin-replaced.png"
    assert replaced.read_bytes() == b"<admin upload>"
