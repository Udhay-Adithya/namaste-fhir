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
    # Prefer English name when present; fallback to term/description heuristics
    display_col = (
        cols_map.get("name english")
        or cols_map.get("english name")
        or cols_map.get("description")
        or cols_map.get("term")
        or next(
            (c for c in columns if "name english" in c.lower()),
            None,
        )
        or next(
            (c for c in columns if "english name" in c.lower()),
            None,
        )
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


def load_icd10_mapping_rows(file_path: Path) -> list[tuple[str, str, str | None]]:
    rows = _read_rows(file_path)
    if not rows:
        return []
    columns = list(rows[0].keys())
    cols_map = {c.lower(): c for c in columns}
    # Try to detect likely columns
    src_code_col = (
        cols_map.get("namaste_code")
        or cols_map.get("ayush_code")
        or cols_map.get("ayurveda_code")
        or next(
            (c for c in columns if "namaste" in c.lower() and "code" in c.lower()), None
        )
        or next(
            (c for c in columns if "ayush" in c.lower() and "code" in c.lower()), None
        )
        or next(
            (c for c in columns if "code" in c.lower() and "ayur" in c.lower()), None
        )
        or next((c for c in columns if c.lower().strip() == "code"), None)
    )
    icd10_code_col = (
        cols_map.get("icd10")
        or cols_map.get("icd-10")
        or cols_map.get("icd 10")
        or next((c for c in columns if "icd" in c.lower() and "10" in c.lower()), None)
    )
    icd10_desc_col = (
        cols_map.get("icd10_description")
        or cols_map.get("icd10_desc")
        or next(
            (
                c
                for c in columns
                if "icd" in c.lower()
                and ("desc" in c.lower() or "title" in c.lower() or "name" in c.lower())
            ),
            None,
        )
    )
    if not (src_code_col and icd10_code_col):
        return []
    out: list[tuple[str, str, str | None]] = []
    for row in rows:
        src_raw = row.get(src_code_col)
        tgt_raw = row.get(icd10_code_col)
        if src_raw is None or tgt_raw is None:
            continue
        src = re.sub(r"\s+", "", str(src_raw).strip())
        tgt = re.sub(r"\s+", "", str(tgt_raw).strip())
        if not src or not tgt or src.lower() == "nan" or tgt.lower() == "nan":
            continue
        desc = (
            str(row.get(icd10_desc_col)).strip()
            if icd10_desc_col and row.get(icd10_desc_col) is not None
            else None
        )
        out.append((src, tgt, desc))
    return out


def load_ayu_synonyms(data_dir: Path) -> dict[str, list[str]]:
    syn_map: dict[str, list[str]] = {}
    for p in sorted(data_dir.glob("ayu-sat-table-*.xlsx")):
        try:
            df = pd.read_excel(p, engine="openpyxl")
        except Exception:
            continue
        cols = [c for c in df.columns]
        lower = {c.lower(): c for c in cols}
        term_col = (
            lower.get("term")
            or lower.get("preferred term")
            or next((c for c in cols if "term" in c.lower()), None)
        )
        syn_col = (
            lower.get("synonym")
            or lower.get("synonyms")
            or next((c for c in cols if "synonym" in c.lower()), None)
        )
        if not term_col or not syn_col:
            continue
        for _, row in df.iterrows():
            term = str(row.get(term_col) or "").strip()
            syns_raw = row.get(syn_col)
            if not term or not syns_raw:
                continue
            syns = []
            if isinstance(syns_raw, str):
                # split on common delimiters
                for part in re.split(r"[,;|]", syns_raw):
                    val = part.strip()
                    if val:
                        syns.append(val)
            elif isinstance(syns_raw, list):
                syns = [str(s).strip() for s in syns_raw if str(s).strip()]
            key = term.lower()
            syn_map.setdefault(key, [])
            for s in syns:
                if s.lower() not in [x.lower() for x in syn_map[key]]:
                    syn_map[key].append(s)
    return syn_map
