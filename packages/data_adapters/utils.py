"""Shared utilities for dataset adapters."""

from __future__ import annotations

import hashlib
import re
import unicodedata
import uuid
from pathlib import Path
from typing import Iterable

import pandas as pd

DATA_EXTENSIONS = {".csv", ".xlsx", ".xls", ".json", ".jsonl", ".parquet", ".pq"}
SKIP_PATH_PARTS = {".git", "__pycache__", "Code"}


def scan_dataset_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    files: list[Path] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in SKIP_PATH_PARTS for part in path.parts):
            continue
        if path.suffix.lower() in DATA_EXTENSIONS:
            files.append(path)
    return files


def clean_column_name(name: str) -> str:
    text = str(name).strip()
    text = text.replace("\ufeff", "").replace("ï»¿", "")
    if text.startswith("Ã¯Â»Â¿"):
        text = text[9:]
    return text.strip()


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [clean_column_name(c) for c in out.columns]
    return out


def normalize_key(text: str) -> str:
    text = clean_column_name(str(text)).lower()
    text = unicodedata.normalize("NFKD", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def find_column(df: pd.DataFrame, candidates: Iterable[str]) -> str | None:
    col_map = {normalize_key(c): c for c in df.columns}
    for cand in candidates:
        key = normalize_key(cand)
        if key in col_map:
            return col_map[key]
    for cand in candidates:
        key = normalize_key(cand)
        for nk, orig in col_map.items():
            if key in nk or nk in key:
                return orig
    return None


def read_tabular(path: Path, nrows: int | None = None) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        for encoding in ("utf-8-sig", "utf-8", "latin-1", "cp1252"):
            try:
                df = pd.read_csv(path, nrows=nrows, encoding=encoding, low_memory=False)
                return normalize_columns(df)
            except UnicodeDecodeError:
                continue
        df = pd.read_csv(path, nrows=nrows, encoding="utf-8", errors="replace", low_memory=False)
        return normalize_columns(df)
    if suffix in {".xlsx", ".xls"}:
        return normalize_columns(pd.read_excel(path, nrows=nrows))
    if suffix in {".parquet", ".pq"}:
        df = pd.read_parquet(path)
        return normalize_columns(df.head(nrows) if nrows else df)
    raise ValueError(f"Unsupported file type: {path}")


def fix_mojibake(text: str | None) -> str | None:
    if text is None or (isinstance(text, float) and pd.isna(text)):
        return None
    s = str(text)
    if "Ã" in s or "Â" in s:
        try:
            return s.encode("latin-1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
    return s


def pg_uuid(external_id: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"supplyguard/real/{external_id}")


def slug_code(text: str, max_len: int = 48) -> str:
    text = normalize_key(text)
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    if not text:
        text = "unknown"
    return text[:max_len]


def stable_id(prefix: str, *parts: str) -> str:
    payload = "|".join(normalize_key(str(p)) for p in parts if p is not None and str(p).strip())
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}-{digest}"


def parse_date_series(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce", utc=False)


def to_iso_date(val) -> str | None:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    ts = pd.to_datetime(val, errors="coerce")
    if pd.isna(ts):
        return None
    return ts.date().isoformat()


def severity_from_delay(delay_days: float | int | None) -> str:
    if delay_days is None or (isinstance(delay_days, float) and pd.isna(delay_days)):
        return "low"
    d = int(delay_days)
    if d <= 0:
        return "low"
    if d <= 3:
        return "medium"
    if d <= 7:
        return "high"
    return "critical"


def empty_frame(columns: list[str]) -> pd.DataFrame:
    return pd.DataFrame(columns=columns)


def ensure_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    out = df.copy()
    for col in columns:
        if col not in out.columns:
            out[col] = None
    return out[columns]
