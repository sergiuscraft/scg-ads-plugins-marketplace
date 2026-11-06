"""CSV helpers: tolerant reading (BOM, delimiter sniffing, header normalisation)."""

from __future__ import annotations

import csv
import io
import re
from pathlib import Path


def _norm_header(h: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", h.strip().lower()).strip("_")


def read_rows(path) -> list[dict]:
    text = Path(path).read_text(encoding="utf-8-sig")
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.reader(io.StringIO(text), dialect)
    rows = [r for r in reader if any(c.strip() for c in r)]
    if not rows:
        return []
    headers = [_norm_header(h) for h in rows[0]]
    return [{headers[i]: (r[i].strip() if i < len(r) else "") for i in range(len(headers))} for r in rows[1:]]


def write_rows(path, rows: list[dict], fieldnames: list[str]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def truthy(value) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y", "neg", "negative"}
