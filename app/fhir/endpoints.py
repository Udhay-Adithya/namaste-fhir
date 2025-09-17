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
    # TODO: integrate Elasticsearch; for now return first matches from DB
    if filter:
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
    vs.expansion = {
        "identifier": request.state.request_id,
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
    mapping = res.scalar_one_or_none()
    if not mapping:
        out = Parameters.construct(
            parameter=[{"name": "result", "valueBoolean": False}]
        )
        return out.dict(exclude_none=True)
    out = Parameters.construct(
        parameter=[
            {"name": "result", "valueBoolean": True},
            {
                "name": "match",
                "part": [
                    {"name": "equivalence", "valueCode": mapping.equivalence},
                    {
                        "name": "concept",
                        "valueCoding": {
                            "system": mapping.target_system,
                            "code": mapping.target_code,
                            "display": mapping.display or mapping.target_code,
                        },
                    },
                ],
            },
        ]
    )
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
