from sqlalchemy import select

from starscream.db.models import LicenseType, Source, TaxonomyNode
from starscream.db.session import get_session_factory
from starscream.pipeline.index import ensure_index
from starscream.storage import ensure_bucket

TAXONOMY_ROOTS = [
    ("WILDLIFE", "Wildlife", "Birds, mammals, insects, fish, reptiles, amphibians"),
    ("NATURAL", "Natural", "Rivers, oceans, forests, geological, wind, silence"),
    ("URBAN", "Urban", "Traffic, crowds, construction, transit, nightlife"),
    ("CULTURAL", "Cultural", "Music, speech, ritual, marketplace, sport, ceremony"),
    ("MECHANICAL", "Mechanical", "Industrial, engines, tools, infrastructure"),
    ("ATMOSPHERIC", "Atmospheric", "Thunder, rain, wind, lightning, aurora"),
    ("AQUATIC", "Aquatic", "Underwater ambience, marine mammals, fish sounds"),
    ("EXTRATERRESTRIAL", "Extraterrestrial", "Space probes, planetary atmospheres"),
]

TAXONOMY_CHILDREN = [
    ("WILDLIFE.BIRD", "Birds", "WILDLIFE"),
    ("WILDLIFE.MAMMAL", "Mammals", "WILDLIFE"),
    ("WILDLIFE.INSECT", "Insects", "WILDLIFE"),
    ("URBAN.TRAFFIC", "Traffic", "URBAN"),
    ("URBAN.CROWD", "Crowds", "URBAN"),
    ("NATURAL.FOREST", "Forest", "NATURAL"),
    ("NATURAL.OCEAN", "Ocean", "NATURAL"),
    ("ATMOSPHERIC.RAIN", "Rain", "ATMOSPHERIC"),
    ("ATMOSPHERIC.THUNDER", "Thunder", "ATMOSPHERIC"),
]

SOURCES = [
    ("Contributor", "contributor", None, LicenseType.CC0),
    ("Freesound", "freesound", "https://freesound.org", LicenseType.CC_BY),
    ("Xeno-canto", "xeno-canto", "https://xeno-canto.org", LicenseType.CC_BY_NC),
    ("iNaturalist", "inaturalist", "https://www.inaturalist.org", LicenseType.CC_BY),
    ("Internet Archive", "internet-archive", "https://archive.org", LicenseType.PUBLIC_DOMAIN),
    ("NOAA", "noaa", "https://www.noaa.gov", LicenseType.PUBLIC_DOMAIN),
    ("NASA", "nasa", "https://www.nasa.gov", LicenseType.PUBLIC_DOMAIN),
    ("FSD50K", "fsd50k", "https://zenodo.org/records/4060432", LicenseType.CC_BY),
    ("ESC-50", "esc50", "https://github.com/karolpiczak/ESC-50", LicenseType.CC_BY_NC),
]


def run_seed() -> None:
    session = get_session_factory()()
    try:
        for code, label, description in TAXONOMY_ROOTS:
            if not session.get(TaxonomyNode, code):
                session.add(
                    TaxonomyNode(code=code, label=label, description=description, parent_code=None)
                )

        for code, label, parent in TAXONOMY_CHILDREN:
            if not session.get(TaxonomyNode, code):
                session.add(
                    TaxonomyNode(code=code, label=label, parent_code=parent)
                )

        for name, slug, url, license_default in SOURCES:
            existing = session.execute(
                select(Source).where(Source.slug == slug)
            ).scalar_one_or_none()
            if not existing:
                session.add(
                    Source(name=name, slug=slug, url=url, license_default=license_default)
                )

        session.commit()
    finally:
        session.close()

    ensure_bucket()
    ensure_index()
    print("Starscream seed complete.")
