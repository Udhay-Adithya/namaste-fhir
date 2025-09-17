import asyncio
from pathlib import Path

from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuditLog, CodeSystem, Base
from app.db.session import AsyncSessionLocal, engine
from app.services.ingest import build_codesystem, load_namaste_codes


DATA_DIR = Path("data")


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def ingest():
    await init_db()
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
    async with AsyncSessionLocal() as session:
        for cs_id, path, url, title in files:
            if not path.exists():
                continue
            concepts = load_namaste_codes(path)
            cs = build_codesystem(cs_id, url, title, concepts)
            await session.execute(
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
                .prefix_with("ON CONFLICT (cs_id) DO NOTHING")
            )
        await session.commit()


if __name__ == "__main__":
    asyncio.run(ingest())
