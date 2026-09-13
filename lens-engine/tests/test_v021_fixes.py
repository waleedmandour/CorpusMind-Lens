"""Regression tests for the v0.2.0 external audit findings (fixed in v0.2.1).

Covers: CSV formula-injection neutralisation (CWE-1236), XML attribute
quoting, phone-redaction precision, the required pseudonym salt, the
companion client version header, and /health capability reporting.
"""
from __future__ import annotations

import csv
import io
import xml.etree.ElementTree as ET

import pytest

import lens_engine
from lens_engine.api.health import optional_stacks
from lens_engine.companion.client import CompanionClient
from lens_engine.export.tabular import render_rows, sanitize_csv_cell, tabulate
from lens_engine.social import ethics


# ── CSV/TSV formula injection (CWE-1236, audit finding #2) ─────────────


def _csv_cells(rows_spec: list[dict]) -> list[str]:
    meta, rows = tabulate({"rows": rows_spec})
    content, _media, _fname = render_rows(meta, rows, "csv", "audit")
    parsed = list(csv.reader(io.StringIO(content.lstrip("\ufeff"))))
    return [r[0] for r in parsed[1:]]


def test_csv_dangerous_cells_are_neutralised():
    payloads = [
        '=HYPERLINK("http://evil.example", "click")',
        "=cmd|'/c calc'!A1",
        "+1+cmd|'/c calc'!A1",
        "@SUM(1+1)*cmd|'/c calc'!A0",
        "-2+3|cmd|'/c calc'!A0",
        "\ttab-prefixed",
        "\rcr-prefixed",
    ]
    cells = _csv_cells([{"text": p} for p in payloads])
    assert len(cells) == len(payloads)
    for original, cell in zip(payloads, cells):
        assert cell.startswith("'"), f"cell not neutralised: {original!r} -> {cell!r}"
        # The payload itself stays readable after the marker quote.
        assert cell[1:] == original


def test_csv_negative_and_positive_numbers_untouched():
    # Corpus statistics export signed numbers everywhere (log ratios, effect
    # sizes); those must remain numeric, not become quoted text.
    values = ["-0.032", "+0.5", "-42", "1.2e-3", "0", "3.14159"]
    cells = _csv_cells([{"logRatio": v} for v in values])
    assert cells == values


def test_tsv_also_neutralised():
    meta, rows = tabulate({"rows": [{"text": "=cmd|'/c calc'!A1"}]})
    content, _media, _fname = render_rows(meta, rows, "tsv", "audit")
    assert "'=cmd" in content.split("\n")[1]  # first data row is neutralised


def test_sanitize_csv_cell_passthrough():
    assert sanitize_csv_cell("plain text") == "plain text"
    assert sanitize_csv_cell("") == ""
    assert sanitize_csv_cell("2024-01-15") == "2024-01-15"


# ── XML attribute quoting (audit finding #4) ────────────────────────────


def test_xml_survives_quotes_and_markup_in_names_and_keys():
    tricky_name = 'project "X" & <reply>'
    tricky_key = 'col"umn & <tag>'
    meta = {tricky_key: "meta & <value>"}
    rows = [{tricky_key: 'He said "hi" & left < right', "text": "=ok"}]
    content, media, _ = render_rows(meta, rows, "xml", tricky_name)
    assert media == "application/xml"
    root = ET.fromstring(content)  # raises if not well-formed
    assert root.get("name") == tricky_name  # and round-trips exactly
    field = root.find("meta/field")
    assert field is not None and field.get("key") == tricky_key


# ── Phone redaction precision (audit finding #5) ────────────────────────


def test_dates_and_numeric_ranges_survive_phone_redaction():
    text = (
        "Fieldwork ran 2024-01-15 to 2024-02-20 (and 15/01/2024 in notes), "
        "ports 8765-8769 checked, cohort 2010-2015."
    )
    assert ethics.redact_text(text) == text


def test_mixed_date_and_phone():
    out = ethics.redact_text("on 2024-01-15 call 0100 123 4567")
    assert "2024-01-15" in out
    assert "[phone]" in out
    assert "4567" not in out.replace("[phone]", "")


def test_phone_numbers_still_redacted():
    for text in (
        "call 0100 123 4567 now",
        "call +20 100 123 4567 now",
        "reach (555) 123-4567 today",
        "whatsapp 0501234567",
    ):
        out = ethics.redact_text(text)
        assert "[phone]" in out, text
        assert "123 4567" not in out and "0501234567" not in out


def test_long_digit_runs_are_kept():
    # 16+ digit runs are order numbers / ids, never E.164 phones.
    text = "order 123456789012345678901234 shipped"
    assert ethics.redact_text(text) == text


# ── Required pseudonym salt (audit finding #9) ──────────────────────────


def test_pseudonymize_handle_requires_salt():
    with pytest.raises(TypeError):
        ethics.pseudonymize_handle("waleed")  # type: ignore[call-arg]
    assert ethics.pseudonymize_handle("Waleed", "s1") == ethics.pseudonymize_handle(
        "waleed ", "s1"
    )
    assert ethics.pseudonymize_handle("Waleed", "s1") != ethics.pseudonymize_handle(
        "Waleed", "s2"
    )
    assert ethics.pseudonymize_handle("", "s1") == ""


# ── Companion client version header (audit finding #7) ──────────────────


def test_companion_client_reports_live_package_version():
    client = CompanionClient("http://127.0.0.1:9999")
    assert client._headers()["X-CorpusMind-Lens-Client"] == (
        f"lens-engine/{lens_engine.__version__}"
    )


# ── /health capability reporting (audit finding #3 visibility) ──────────


def test_optional_stacks_shape():
    caps = optional_stacks()
    assert set(caps) == {"vision_models", "alignment_embeddings", "tesseract_ocr"}
    for entry in caps.values():
        assert isinstance(entry["available"], bool)
        assert entry["enables"].strip()
        assert entry["enable_hint"].strip()
        assert isinstance(entry["packages"], dict)


def test_health_endpoint_reports_capabilities(app_client):
    r = app_client.get("/api/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    caps = body.get("capabilities")
    assert isinstance(caps, dict) and "vision_models" in caps
    # available must honestly mirror the underlying package probe
    assert caps["vision_models"]["available"] == all(
        caps["vision_models"]["packages"].values()
    )
