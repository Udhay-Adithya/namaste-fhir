from pathlib import Path
from typing import Iterable
import re

import pandas as pd
from fhir.resources.codesystem import CodeSystem
from fhir.resources.conceptmap import ConceptMap


def _read_rows(file_path: Path) -> list[dict]:
    suffix = file_path.suffix.lower()
    if suffix == ".xls":
        import xlrd  # type: ignore

        wb = xlrd.open_workbook(str(file_path))
        sheet = wb.sheet_by_index(0)
        headers = [str(h).strip() for h in sheet.row_values(0)]
        rows: list[dict] = []
        for r in range(1, sheet.nrows):
            vals = sheet.row_values(r)
            row = {headers[i]: vals[i] for i in range(min(len(headers), len(vals)))}
            rows.append(row)
        return rows
    else:
        df = pd.read_excel(file_path, engine="openpyxl")
        return df.to_dict(orient="records")


def load_namaste_codes(file_path: Path) -> list[dict]:
    rows = _read_rows(file_path)
    if not rows:
        return []
    columns = list(rows[0].keys())
    cols_map = {c.lower(): c for c in columns}
    code_col = cols_map.get("code") or next(
        (c for c in columns if "code" in c.lower()), None
    )
    display_col = (
        cols_map.get("description")
        or cols_map.get("term")
        or next(
            (c for c in columns if "desc" in c.lower() or "name" in c.lower()), None
        )
    )
    definition_col = cols_map.get("definition") or None
    items: list[dict] = []
    for row in rows:
        raw_code = row.get(code_col) if code_col else None
        code = str(raw_code).strip() if raw_code is not None else ""
        if not code or code.lower() == "nan":
            continue
        code = re.sub(r"\s+", "", code)
        raw_display = row.get(display_col) if display_col else None
        display = str(raw_display).strip() if raw_display is not None else code
        raw_def = row.get(definition_col) if definition_col else None
        definition = str(raw_def).strip() if raw_def is not None else None
        concept = {"code": code, "display": display}
        if definition:
            concept["definition"] = definition
        items.append(concept)
    return items


def build_codesystem(
    cs_id: str, url: str, title: str, concepts: list[dict]
) -> CodeSystem:
    payload = {
        "resourceType": "CodeSystem",
        "id": cs_id,
        "url": url,
        "version": "1.0.0",
        "name": cs_id.replace("-", "").title(),
        "title": title,
        "status": "active",
        "content": "complete",
        "concept": concepts,
    }
    return CodeSystem(**payload)


def build_conceptmap(
    cm_id: str,
    url: str,
    source_cs: str,
    target_cs: str,
    mappings: Iterable[tuple[str, str, str | None]],
) -> ConceptMap:
    group = {"source": source_cs, "target": target_cs, "element": []}
    for src, tgt, disp in mappings:
        group["element"].append(
            {
                "code": src,
                "target": [
                    {"code": tgt, "display": disp or tgt, "equivalence": "relatedto"}
                ],
            }
        )
    payload = {
        "resourceType": "ConceptMap",
        "id": cm_id,
        "url": url,
        "status": "active",
        "group": [group],
    }
    return ConceptMap(**payload)
