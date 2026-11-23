#!/usr/bin/env python3
"""Turn CPCB hourly AQI workbooks into the files the API and annual views read.

Run from the repository root:

    backend/.venv/bin/python scripts/ingest_cpcb_hourly_aqi.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.ingestion.cpcb_hourly_aqi import build_extract  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest CPCB hourly AQI workbooks")
    parser.add_argument("--source", type=Path, default=ROOT / "cpcb_data_2025_2026")
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "processed" / "cpcb_aqi")
    parser.add_argument("--raw", type=Path, default=ROOT / "data" / "raw")
    args = parser.parse_args()
    report = build_extract(args.source, args.output, args.raw)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
