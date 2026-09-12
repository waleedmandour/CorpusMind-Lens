"""Export routes (§9.19): per-image and per-set exports, battery CSV/XML
exports for every analysis result, and the Methods Section."""
from __future__ import annotations

import csv
import io
import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from ..export.methods import methods_paragraph
from ..export.tabular import render_rows, tabulate
from ..main import get_store
from ..vision.annotations import read_annotations

router = APIRouter(tags=["export"])


def _flatten(meta: dict) -> dict:
    ann = read_annotations(meta)
    dims = {f"annotation:{k}": ",".join((v or {}).get("values") or [])
            for k, v in (ann["dimensions"] or {}).items()}
    return {
        "tags": ",".join(ann["tags"]),
        "ocr_text": (meta.get("ocr") or {}).get("text", ""),
        "ocr_confidence": (meta.get("ocr") or {}).get("confidence", 0.0),
        "ocr_language": (meta.get("ocr") or {}).get("language", ""),
        "dominant_colours": ",".join(
            c.get("hex", "") for c in (meta.get("colour") or {}).get("dominant_colours", [])),
        "warm_cold_balance": (meta.get("colour") or {}).get("warm_cold_balance"),
        "brightness": (meta.get("colour") or {}).get("brightness"),
        "contrast": (meta.get("colour") or {}).get("contrast"),
        "info_left": ((meta.get("composition") or {}).get("information_value") or {}).get("left"),
        "info_right": ((meta.get("composition") or {}).get("information_value") or {}).get("right"),
        "info_top": ((meta.get("composition") or {}).get("information_value") or {}).get("top"),
        "info_bottom": ((meta.get("composition") or {}).get("information_value") or {}).get("bottom"),
        "detections": json.dumps(
            [{"label": d.get("label"), "confidence": d.get("confidence"),
              "bbox": d.get("bbox")} for d in meta.get("detections", [])],
            ensure_ascii=False),
        "vlm_description": (meta.get("vlm_description") or {}).get("text", ""),
        **dims,
    }


@router.get("/images/{image_id}/export")
async def export_image(image_id: str, format: str = "json") -> Response:
    store = get_store()
    img = store.get_image(image_id)
    if not img:
        raise HTTPException(404, "Image not found")
    row = {"image_id": img.id, "filename": img.filename, "width": img.width,
           "height": img.height, "format": img.format, "created_at": img.created_at,
           **_flatten(img.meta or {})}
    return _render([row], format, f"lens-image-{image_id}")


@router.get("/imagesets/{set_id}/export")
async def export_set(set_id: str, format: str = "xlsx") -> Response:
    store = get_store()
    s = store.get_image_set(set_id)
    if not s:
        raise HTTPException(404, "Image set not found")
    rows = []
    for img in store.list_images(set_id):
        rows.append({"image_id": img.id, "filename": img.filename, "width": img.width,
                     "height": img.height, "format": img.format,
                     "created_at": img.created_at, **_flatten(img.meta or {})})
    return _render(rows, format, f"lens-set-{set_id}")


@router.get("/imagesets/{set_id}/methods-section")
async def methods_section(set_id: str) -> dict:
    """Auto-drafted Methods paragraph naming exact models/versions (§9.19)."""
    store = get_store()
    s = store.get_image_set(set_id)
    if not s:
        raise HTTPException(404, "Image set not found")
    images = store.list_images(set_id)
    from ..api.imagesets import image_set_stats

    stats = await image_set_stats(set_id)
    return {"methods": methods_paragraph(stats, [i.meta or {} for i in images])}


def _render(rows: list[dict], format: str, name: str) -> Response:
    fmt = format.lower()
    if not rows:
        raise HTTPException(404, "Nothing to export")
    if fmt == "json":
        return Response(content=json.dumps(rows, ensure_ascii=False, indent=2),
                        media_type="application/json",
                        headers={"Content-Disposition": f'attachment; filename="{name}.json"'})
    columns = sorted({k for r in rows for k in r})
    if fmt in ("csv", "tsv"):
        delim = "\t" if fmt == "tsv" else ","
        buf = io.StringIO()
        if fmt == "csv":
            buf.write("\ufeff")  # UTF-8 BOM so Excel opens UTF-8 correctly
        writer = csv.DictWriter(buf, fieldnames=columns, delimiter=delim)
        writer.writeheader()
        writer.writerows(rows)
        return Response(content=buf.getvalue(), media_type=f"text/{fmt}",
                        headers={"Content-Disposition": f'attachment; filename="{name}.{fmt}"'})
    if fmt == "xlsx":
        from openpyxl import Workbook  # base dependency since v0.1.0 (xlsx export is a first-class feature)

        wb = Workbook()
        ws = wb.active
        ws.title = "lens-export"
        ws.append(columns)
        for r in rows:
            ws.append([r.get(c) for c in columns])
        buf = io.BytesIO()
        wb.save(buf)
        return Response(content=buf.getvalue(),
                        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        headers={"Content-Disposition": f'attachment; filename="{name}.xlsx"'})
    if fmt == "txt":
        body = "\n".join(json.dumps(r, ensure_ascii=False) for r in rows)
        return Response(content=body, media_type="text/plain",
                        headers={"Content-Disposition": f'attachment; filename="{name}.txt"'})
    if fmt == "xml":
        content, media_type, filename = render_rows({}, rows, "xml", name)
        return Response(content=content, media_type=media_type,
                        headers={"Content-Disposition": f'attachment; filename="{filename}"'})
    raise HTTPException(422, f"Unsupported export format: {format} (xlsx/csv/tsv/xml/txt/json)")


# --------------------------------------------------------------------------- #
# Battery exports: CSV/XML/TSV/JSON for every analysis result (v0.2)
# --------------------------------------------------------------------------- #


def _set_images(set_id: str):
    store = get_store()
    if not store.get_image_set(set_id):
        raise HTTPException(404, "Image set not found")
    return store.list_images(set_id)


@router.get("/imagesets/{set_id}/battery-export/{kind}")
async def export_battery(
    set_id: str,
    kind: str,
    format: str = "csv",
    dim: str = "",
    dim_b: str = "",
    reference_set_id: str = "",
    category: str = "",
    n: int = 2,
    min_count: int = 2,
    include_gaps: bool = True,
    bins: int = 10,
    context: int = 2,
) -> Response:
    """Export any battery result (CSV/TSV/XML/JSON). Mirrors the battery
    routes so every Workbench outcome is exportable for the methods section
    and for external analysis (v0.2 requirement)."""
    from ..stats import service

    images = _set_images(set_id)
    fmt = format.lower()
    if fmt not in ("csv", "tsv", "xml", "json"):
        raise HTTPException(422, "format must be one of: csv, tsv, xml, json")

    def _need(value: str, label: str) -> str:
        if not value:
            raise HTTPException(422, f"{label} is required for {kind}")
        return value

    try:
        if kind == "frequency":
            result = service.frequency_profile(images, _need(dim, "dim"))
        elif kind == "diversity":
            result = service.diversity_battery(images, _need(dim, "dim"))
        elif kind == "ngrams":
            result = service.ngrams(images, _need(dim, "dim"), n=n, min_count=min_count, include_gaps=include_gaps)
        elif kind == "cooccurrence":
            result = service.cooccurrence(images, _need(dim, "dim"), _need(dim_b, "dim_b"), min_joint=min_count)
        elif kind == "keyness":
            result = service.keyness(images, _set_images(_need(reference_set_id, "reference_set_id")), _need(dim, "dim"))
        elif kind == "dispersion":
            result = service.dispersion(images, _need(dim, "dim"), bins=bins)
        elif kind == "kwic":
            result = service.visual_kwic(images, _need(dim, "dim"), _need(category, "category"), context=context)
        elif kind == "full":
            result = {
                "dimension": dim,
                "frequency": service.frequency_profile(images, dim),
                "diversity": service.diversity_battery(images, dim),
                "ngrams": service.ngrams(images, dim, n=n, min_count=1),
                "dispersion": service.dispersion(images, dim),
            }
        else:
            raise HTTPException(404, f"Unknown battery kind: {kind}")
    except ValueError as e:
        raise HTTPException(422, str(e))

    name = f"lens-battery-{kind}-{set_id}"
    try:
        meta, rows = tabulate(result)
        content, media_type, filename = render_rows(meta, rows, fmt, name)
    except ValueError as e:
        raise HTTPException(422, str(e))
    return Response(content=content, media_type=media_type,
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})
