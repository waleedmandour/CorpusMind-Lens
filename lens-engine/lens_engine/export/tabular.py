"""Generic tabular rendering for analysis results (CSV / XML / TSV / JSON).

Every corpus-analysis outcome (battery results, social analytics, KWIC,
networks) is a JSON document mixing scalar metadata with lists of record
rows. :func:`tabulate` extracts a uniform row shape so any result exports
cleanly; :func:`render_rows` serialises it. Used by the export routes and
the Social tab exports.
"""
from __future__ import annotations

import csv
import io
import json
import re
from typing import Any
from xml.sax.saxutils import escape, quoteattr

# CSV/Formula injection (CWE-1236): cells beginning with = + - @ (or a tab /
# CR) are executed as formulas by Excel, LibreOffice Calc and Google Sheets
# when the file is opened. Lens exports are full of third-party text (social
# posts, OCR output) the researcher does NOT control, so every cell is
# neutralised on the way out. Leading `-`/`+` on a purely numeric value is
# exempt: corpus statistics are full of ordinary negative numbers (log
# ratios, effect sizes) and those are constants, not executable formulas.
_FORMULA_RISK_PREFIXES = ("=", "@", "\t", "\r")
_SIGNED_NUMBER = re.compile(r"^[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?$")


def sanitize_csv_cell(value: str) -> str:
    """Return ``value`` made safe to open in a spreadsheet application.

    Cells that could be interpreted as formulas are prefixed with a single
    quote (the standard mitigation recommended by OWASP for CSV export);
    spreadsheets then treat the whole cell as literal text and display the
    original content. Purely numeric values (including signed ones) pass
    through untouched so researchers can keep computing on exported
    statistics.
    """
    if not value:
        return value
    first = value[0]
    if first in _FORMULA_RISK_PREFIXES:
        return "'" + value
    if first in "+-" and not _SIGNED_NUMBER.match(value):
        return "'" + value
    return value


def tabulate(result: Any) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Return (meta, rows). ``rows`` is the dominant list of dicts; ``meta``
    carries the remaining scalar context. Nested non-dominant lists are
    JSON-encoded into their row so no data silently disappears."""
    if isinstance(result, list):
        return {}, [r if isinstance(r, dict) else {"value": r} for r in result]
    if not isinstance(result, dict):
        return {"value": result}, []

    lists = {k: v for k, v in result.items() if isinstance(v, list)}
    meta = {k: v for k, v in result.items() if k not in lists}

    if not lists:
        return meta, []

    # Prefer a list of dicts with the most keys as the record table.
    def _score(item: list) -> int:
        dicts = [x for x in item if isinstance(x, dict)]
        if not dicts:
            return -1
        return max(len(d) for d in dicts) * 1000 + len(item)

    best_key = max(lists, key=lambda k: _score(lists[k]))
    best = lists[best_key]
    if not any(isinstance(x, dict) for x in best):
        meta[best_key] = json.dumps(best, ensure_ascii=False)
        return meta, [{"index": i, "value": v} for i, v in enumerate(best)]

    rows: list[dict[str, Any]] = []
    for item in best:
        if isinstance(item, dict):
            row = dict(item)
        else:
            row = {"value": item}
        for k, v in result.items():
            if k in lists and k != best_key:
                row[k] = json.dumps(v, ensure_ascii=False)
        rows.append(row)
    return meta, rows


def render_rows(
    meta: dict[str, Any],
    rows: list[dict[str, Any]],
    fmt: str,
    name: str,
) -> tuple[str, str, str]:  # (content, media_type, filename)
    fmt = fmt.lower()
    columns = sorted({k for r in rows for k in r}) or ["value"]

    if fmt == "json":
        doc = {"meta": meta, "rows": rows}
        return (
            json.dumps(doc, ensure_ascii=False, indent=2),
            "application/json",
            f"{name}.json",
        )

    if fmt in ("csv", "tsv"):
        delim = "\t" if fmt == "tsv" else ","
        buf = io.StringIO()
        if fmt == "csv":
            buf.write("﻿")  # UTF-8 BOM so Excel opens UTF-8 correctly
        writer = csv.DictWriter(buf, fieldnames=columns, delimiter=delim, extrasaction="ignore")
        writer.writeheader()
        for r in rows:
            # _scalar normalises dicts/lists to JSON text; sanitize_csv_cell
            # then defuses formula injection (corpus text is adversarial).
            writer.writerow(
                {k: sanitize_csv_cell(_scalar(r.get(k, ""))) for k in columns}
            )
        return buf.getvalue(), f"text/{fmt}", f"{name}.{fmt}"

    if fmt == "xml":
        # Attribute values go through quoteattr (NOT escape): escape() leaves
        # double quotes intact, so any user-controlled name/key containing a
        # `"` broke out of the attribute and produced invalid XML (v0.2.0
        # finding). quoteattr picks the safe quoting and escapes everything
        # needed, including the quote character itself.
        parts = [f'<?xml version="1.0" encoding="UTF-8"?>', f"<result name={quoteattr(name)}>"]
        parts.append("  <meta>")
        for k, v in meta.items():
            parts.append(f"    <field key={quoteattr(str(k))}>{escape(_scalar(v))}</field>")
        parts.append("  </meta>")
        parts.append(f'  <rows count="{len(rows)}">')
        for i, r in enumerate(rows, 1):
            parts.append(f'    <row index="{i}">')
            for c in columns:
                parts.append(f"      <{safe_tag(c)}>{escape(_scalar(r.get(c, '')))}</{safe_tag(c)}>")
            parts.append("    </row>")
        parts.append("  </rows>")
        parts.append("</result>")
        return "\n".join(parts), "application/xml", f"{name}.xml"

    raise ValueError(f"Unsupported export format: {fmt}")


def _scalar(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, (dict, list)):
        return json.dumps(v, ensure_ascii=False)
    return str(v)


def safe_tag(column: str) -> str:
    out = []
    for ch in column:
        if ch.isalnum() or ch in "_-":
            out.append(ch)
        else:
            out.append("_")
    name = "".join(out) or "field"
    if not (name[0].isalpha() or name[0] == "_"):
        name = "c_" + name
    return name
