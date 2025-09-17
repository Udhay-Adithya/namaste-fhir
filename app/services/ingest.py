from pathlib import Path
from typing import Iterable

import pandas as pd
from fhir.resources.codesystem import CodeSystem
from fhir.resources.conceptmap import ConceptMap


def load_namaste_codes(file_path: Path) -> list[dict]:
    df = pd.read_excel(file_path)
    cols = {c.lower(): c for c in df.columns}
    code_col = cols.get("code") or next(
        (c for c in df.columns if "code" in c.lower()), None
    )
    display_col = (
        cols.get("description")
        or cols.get("term")
        or next(
            (c for c in df.columns if "desc" in c.lower() or "name" in c.lower()), None
        )
    )
    definition_col = cols.get("definition") or None
    items: list[dict] = []
    for _, row in df.iterrows():
        code = str(row.get(code_col)).strip()
        if not code or code.lower() == "nan":
            continue
        display = str(row.get(display_col)).strip() if display_col else code
        definition = str(row.get(definition_col)).strip() if definition_col else None
        concept = {"code": code, "display": display}
        if definition:
            concept["definition"] = definition
        items.append(concept)
    return items


def build_codesystem(
    cs_id: str, url: str, title: str, concepts: list[dict]
) -> CodeSystem:
    cs = CodeSystem.construct()
    cs.id = cs_id
    cs.url = url
    cs.version = "1.0.0"
    cs.name = cs_id.replace("-", "").title()
    cs.title = title
    cs.status = "active"
    cs.content = "complete"
    cs.concept = concepts
    return cs


def build_conceptmap(
    cm_id: str,
    url: str,
    source_cs: str,
    target_cs: str,
    mappings: Iterable[tuple[str, str, str | None]],
) -> ConceptMap:
    cm = ConceptMap.construct()
    cm.id = cm_id
    cm.url = url
    cm.status = "active"
    group = {
        "source": source_cs,
        "target": target_cs,
        "element": [],
    }
    for src, tgt, disp in mappings:
        group["element"].append(
            {
                "code": src,
                "target": [
                    {"code": tgt, "display": disp or tgt, "equivalence": "relatedto"}
                ],
            }
        )
    cm.group = [group]
    return cm
