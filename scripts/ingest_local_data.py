import asyncio
from pathlib import Path

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuditLog, CodeSystem, Base, Mapping
from app.db.session import AsyncSessionLocal, engine
from app.services.ingest import build_codesystem, load_namaste_codes
from app.services.ingest import load_ayu_synonyms
from app.services.search import bulk_index
from app.config import get_settings


DATA_DIR = Path("data")


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def ingest():
    await init_db()
    settings = get_settings()
    files = [
        (
            "namaste-ayurveda",
            DATA_DIR / "Morbidity_Codes_Ayurveda.xls",
            "https://namaste.ayush.gov.in/fhir/CodeSystem/ayurveda",
            "NAMASTE Ayurveda Morbidity Codes",
        ),
        (
            "namaste-siddha",
            DATA_DIR / "Morbidity_Codes_Siddha.xls",
            "https://namaste.ayush.gov.in/fhir/CodeSystem/siddha",
            "NAMASTE Siddha Morbidity Codes",
        ),
        (
            "namaste-unani",
            DATA_DIR / "Morbidity_Codes_Unani.xls",
            "https://namaste.ayush.gov.in/fhir/CodeSystem/unani",
            "NAMASTE Unani Morbidity Codes",
        ),
    ]
    synonyms_map = load_ayu_synonyms(DATA_DIR)
    search_docs: list[dict] = []
    async with AsyncSessionLocal() as session:
        for cs_id, path, url, title in files:
            if not path.exists():
                continue
            concepts = load_namaste_codes(path)
            cs = build_codesystem(cs_id, url, title, concepts)
            stmt = (
                insert(CodeSystem)
                .values(
                    cs_id=cs_id,
                    url=url,
                    version=cs.version,
                    name=cs.name,
                    title=cs.title,
                    status=cs.status,
                    content=cs.dict(exclude_none=True),
                )
                .on_conflict_do_nothing(index_elements=[CodeSystem.cs_id])
            )
            await session.execute(stmt)
            # prepare ES docs
            for c in concepts:
                search_docs.append(
                    {
                        "system": url,
                        "code": c.get("code"),
                        "display": c.get("display"),
                        "synonyms": synonyms_map.get(
                            str(c.get("display", "")).lower(), []
                        ),
                    }
                )
        # ICD-10 crosswalk ingestion removed; rely on ICD-11 API at translate time
        await session.commit()
    # Index to Elasticsearch (if available)
    if search_docs:
        try:
            bulk_index(settings.search_index_name, search_docs)
        except Exception as e:
            print(f"[warn] indexing skipped: {e}")


if __name__ == "__main__":
    asyncio.run(ingest())
