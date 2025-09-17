from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fhir.resources.parameters import Parameters
from fhir.resources.valueset import ValueSet
from fhir.resources.bundle import Bundle
from fhir.resources.codesystem import CodeSystem

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.session import get_db
from ..db.models import CodeSystem as CSModel, Mapping as MappingModel
from ..security import get_current_user
from ..services.search import autocomplete as es_autocomplete
from ..services.icd11 import fetch_icd11_concept, search_icd11, autocode_icd11
from ..config import get_settings


router = APIRouter(prefix="/fhir", tags=["FHIR"])


@router.get("/CodeSystem/{cs_id}", response_model=dict)
async def get_codesystem(
    cs_id: str, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    res = await db.execute(select(CSModel).where(CSModel.cs_id == cs_id))
    row = res.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="CodeSystem not found")
    return row.content


@router.get("/ValueSet/$expand", response_model=dict)
async def valueset_expand(
    request: Request,
    url: str = Query(...),
    filter: str | None = Query(None, alias="filter"),
    count: int = Query(10),
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    vs = ValueSet.construct(id="expand-result", url=url, status="active")
    contains = []
    if filter:
        # Try Elasticsearch first
        try:
            settings = get_settings()
            hits = es_autocomplete(settings.search_index_name, filter, size=count)
            for h in hits:
                contains.append(
                    {
                        "system": h.get("system"),
                        "code": h.get("code"),
                        "display": h.get("display"),
                    }
                )
        except Exception:
            hits = []
        # Fallback to DB LIKE search if ES empty
        if not contains:
            res = await db.execute(select(CSModel))
            for cs in res.scalars():
                for c in (cs.content or {}).get("concept", []):
                    disp = c.get("display", "")
                    if filter.lower() in disp.lower():
                        contains.append(
                            {
                                "system": cs.content.get("url"),
                                "code": c.get("code"),
                                "display": disp,
                            }
                        )
                        if len(contains) >= count:
                            break
                if len(contains) >= count:
                    break
    from datetime import datetime, timezone

    vs.expansion = {
        "identifier": request.state.request_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total": len(contains),
        "contains": contains[:count],
    }
    return vs.dict(exclude_none=True)


@router.post("/ConceptMap/$translate", response_model=dict)
async def conceptmap_translate(
    params: dict, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    try:
        parameters = Parameters(**params)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    url = next(
        (
            p.valueUri
            for p in parameters.parameter
            if p.name == "url" and getattr(p, "valueUri", None)
        ),
        None,
    )
    code = next(
        (
            p.valueCode
            for p in parameters.parameter
            if p.name == "code" and getattr(p, "valueCode", None)
        ),
        None,
    )
    system = next(
        (
            p.valueUri
            for p in parameters.parameter
            if p.name == "system" and getattr(p, "valueUri", None)
        ),
        None,
    )
    if not (url and code and system):
        raise HTTPException(
            status_code=400, detail="Missing url, code, or system parameter"
        )
    res = await db.execute(
        select(MappingModel).where(
            MappingModel.source_system == system,
            MappingModel.source_code == code,
        )
    )
    mappings = list(res.scalars())
    if not mappings:
        # Try ICD-API autocode (TM2 first, then MMS) using the source display
        src_display = None
        res_cs = await db.execute(select(CSModel))
        for cs in res_cs.scalars():
            if cs.content and cs.content.get("url") == system:
                for c in (cs.content or {}).get("concept", []):
                    if c.get("code") == code:
                        src_display = c.get("display")
                        break
        best_effort = None
        search_system = None
        if src_display:
            try:
                ac = autocode_icd11(src_display, linearization="tm2")
                if not ac or not ac.get("theCode"):
                    ac = autocode_icd11(src_display, linearization="mms")
                    if ac and ac.get("theCode"):
                        search_system = "http://id.who.int/icd/release/11/mms"
                else:
                    search_system = "http://id.who.int/icd/release/11/tm2"
                if ac and ac.get("theCode"):
                    best_effort = ac
            except Exception:
                best_effort = None
        if best_effort:
            out = Parameters.construct(
                parameter=[
                    {"name": "result", "valueBoolean": True},
                    {
                        "name": "match",
                        "part": [
                            {"name": "equivalence", "valueCode": "relatedto"},
                            {
                                "name": "concept",
                                "valueCoding": {
                                    "system": search_system
                                    or "http://id.who.int/icd/release/11/mms",
                                    "code": best_effort.get("theCode")
                                    or best_effort.get("code")
                                    or best_effort.get("id")
                                    or "",
                                    "display": (
                                        best_effort.get("matchingText")
                                        or best_effort.get("label")
                                        or best_effort.get("title")
                                        or (best_effort.get("title", {}) or {}).get(
                                            "@value"
                                        )
                                        or best_effort.get("theCode")
                                    ),
                                },
                            },
                        ],
                    },
                    {
                        "name": "message",
                        "valueString": "Returned ICD-11 best-effort match via WHO ICD-API autocode.",
                    },
                ]
            )
            return out.dict(exclude_none=True)
        out = Parameters.construct(
            parameter=[{"name": "result", "valueBoolean": False}]
        )
        return out.dict(exclude_none=True)

    # Prefer ICD-11 targets if present; otherwise include ICD-10
    def is_icd11(sys: str | None) -> bool:
        return bool(sys and sys.startswith("http://id.who.int/icd/release/11/"))

    ordered = sorted(mappings, key=lambda m: 0 if is_icd11(m.target_system) else 1)
    parts = []
    for m in ordered:
        parts.append(
            {
                "name": "match",
                "part": [
                    {"name": "equivalence", "valueCode": m.equivalence},
                    {
                        "name": "concept",
                        "valueCoding": {
                            "system": m.target_system,
                            "code": m.target_code,
                            "display": m.display or m.target_code,
                        },
                    },
                ],
            }
        )

    parameters = [{"name": "result", "valueBoolean": True}] + parts

    # Optional: if only ICD-10 is found, we could attempt ICD-11 fetch/bridge (placeholder)
    if parameters and not any(is_icd11(m.target_system) for m in ordered):
        # Example of including an advisory message
        parameters.append(
            {
                "name": "message",
                "valueString": "ICD-11 mapping not found; returning ICD-10 related mapping.",
            }
        )

    out = Parameters.construct(parameter=parameters)
    return out.dict(exclude_none=True)


@router.post("/Bundle", response_model=dict)
async def post_bundle(
    bundle: dict, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    try:
        b = Bundle(**bundle)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"resourceType": "Bundle", "type": b.type, "total": len(b.entry or [])}
