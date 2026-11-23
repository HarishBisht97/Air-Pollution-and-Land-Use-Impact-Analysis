"""CPCB station workbooks of hourly AQI for Delhi, 2025–2026.

Each workbook is one station-month. Rows are days, columns are hours, and the
numbers are the CPCB hourly AQI index. They are not concentrations in µg/m³.
Blank hours are omitted. A day is kept in the daily file only when it has at
least 16 hours, the same bar used for the concentration-based daily means.
"""

from __future__ import annotations

import csv
import gzip
import json
import re
import zipfile
from calendar import monthrange
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from statistics import fmean
from typing import Any
from xml.etree import ElementTree as ET
from zoneinfo import ZoneInfo

from app.analytics.daily_aqi import MIN_DAYS, annual_from_daily

SOURCE = "CPCB CCR station hourly AQI"
VALUE_KIND = "aqi_index"
TIMEZONE_NAME = "Asia/Kolkata"
IST = ZoneInfo(TIMEZONE_NAME)
MIN_HOURS = 16
AQI_MIN = 0.0
AQI_MAX = 500.0
HOURLY_AQI_FROM_YEAR = 2025
PARTIAL_YEAR = 2026
COVERAGE_END = "2026-10-31"
COVERAGE_NOTE = "Through 31 October 2026. November and December are not in this download."

_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_MONTHS = {
    "January": 1,
    "February": 2,
    "March": 3,
    "April": 4,
    "May": 5,
    "June": 6,
    "July": 7,
    "August": 8,
    "September": 9,
    "October": 10,
    "November": 11,
    "December": 12,
}
_FILENAME = re.compile(
    r"^AQI_Data_Station_Level_Site_(?P<site>\d+)_(?P<name>.+)_Delhi_(?P<agency>[A-Za-z0-9]+)_"
    r"(?P<month>January|February|March|April|May|June|July|August|September|October|November|December)_"
    r"(?P<year>\d{4})_Hourly(?: \(\d+\))?$"
)
_DUPLICATE = re.compile(r" \(\d+\)(\.xlsx)$", re.IGNORECASE)
_BLANK = {"", "NA", "NONE", "NULL", "-", "NAN"}


@dataclass
class HourlySheet:
    site_id: str
    name: str
    agency: str
    year: int
    month: int
    hours: dict[datetime, float] = field(default_factory=dict)
    rejected: int = 0


def normalize_name(name: str) -> str:
    text = name.lower().replace("_", " ").replace("-", " ").replace(".", " ")
    return " ".join(text.split(",")[0].split())


def canonical_station_id(value: str) -> str:
    text = value.strip()
    if text.lower().startswith("site_"):
        return "site_" + text.split("_", 1)[1]
    if text.isdigit():
        return f"site_{text}"
    return text


def choose_workbooks(paths: list[Path]) -> tuple[list[Path], int]:
    """Drop a ` (1)` download when the unsuffixed workbook is present."""
    names = {path.name for path in paths}
    kept: list[Path] = []
    skipped = 0
    for path in sorted(paths, key=lambda item: item.name):
        match = _DUPLICATE.search(path.name)
        if match is not None and path.name[: match.start()] + match.group(1) in names:
            skipped += 1
            continue
        kept.append(path)
    return kept, skipped


def _column_index(ref: str) -> int:
    letters = "".join(char for char in ref if char.isalpha())
    value = 0
    for char in letters:
        value = value * 26 + (ord(char.upper()) - 64)
    return value - 1


def _shared_strings(archive: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    strings = []
    for item in root.findall(f"{_NS}si"):
        strings.append("".join(node.text or "" for node in item.iter(f"{_NS}t")))
    return strings


def _cell_text(cell: ET.Element, shared: list[str]) -> str | None:
    kind = cell.get("t")
    if kind == "inlineStr":
        text = "".join(node.text or "" for node in cell.iter(f"{_NS}t")).strip()
        return text or None
    value = cell.find(f"{_NS}v")
    if value is None or value.text is None or value.text.strip() == "":
        return None
    if kind == "s":
        return shared[int(value.text)].strip()
    return value.text.strip()


def _parse_aqi(text: str) -> float | None:
    """Return the index, or None when the cell is blank. Raise on a bad value."""
    if text.strip().upper() in _BLANK:
        return None
    value = float(text)
    if value < AQI_MIN or value > AQI_MAX:
        raise ValueError(f"AQI outside {AQI_MIN:g}–{AQI_MAX:g}: {text}")
    return value


def _sheet_rows(path: Path) -> list[dict[int, str]]:
    with zipfile.ZipFile(path) as archive:
        shared = _shared_strings(archive)
        root = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
    rows: list[dict[int, str]] = []
    for row in root.findall(f"{_NS}sheetData/{_NS}row"):
        cells: dict[int, str] = {}
        for position, cell in enumerate(row.findall(f"{_NS}c")):
            ref = cell.get("r")
            index = _column_index(ref) if ref else position
            text = _cell_text(cell, shared)
            if text is not None:
                cells[index] = text
        rows.append(cells)
    return rows


def read_workbook(path: Path) -> HourlySheet:
    match = _FILENAME.match(path.stem)
    if match is None:
        raise ValueError(f"Unrecognized CPCB workbook name: {path.name}")
    year = int(match.group("year"))
    month = _MONTHS[match.group("month")]
    sheet = HourlySheet(
        site_id=match.group("site"),
        name=match.group("name").replace("_", " "),
        agency=match.group("agency"),
        year=year,
        month=month,
    )
    last_day = monthrange(year, month)[1]
    for cells in _sheet_rows(path):
        day_text = cells.get(0)
        if day_text is None:
            continue
        try:
            day = int(float(day_text))
        except ValueError:
            continue
        if day < 1 or day > last_day:
            sheet.rejected += 1
            continue
        for column, text in cells.items():
            if column < 1 or column > 24:
                continue
            try:
                value = _parse_aqi(text)
            except ValueError:
                sheet.rejected += 1
                continue
            if value is None:
                continue
            stamp = datetime(year, month, day, column - 1, tzinfo=IST)
            sheet.hours[stamp] = value
    return sheet


def daily_from_hours(station_id: str, hours: dict[datetime, float], min_hours: int = MIN_HOURS) -> list[dict]:
    grouped: dict[str, list[float]] = defaultdict(list)
    for stamp, value in hours.items():
        grouped[stamp.date().isoformat()].append(value)
    rows = []
    for day in sorted(grouped):
        values = grouped[day]
        if len(values) < min_hours:
            continue
        rows.append(
            {
                "station_id": station_id,
                "day": day,
                "mean": round(fmean(values), 1),
                "max": round(max(values), 1),
                "n": len(values),
            }
        )
    return rows


def monthly_from_daily(rows: list[dict]) -> list[dict]:
    grouped: dict[tuple[str, str], list[float]] = defaultdict(list)
    for row in rows:
        grouped[(row["station_id"], row["day"][:7])].append(float(row["mean"]))
    monthly = []
    for station_id, month in sorted(grouped):
        values = grouped[(station_id, month)]
        monthly.append(
            {
                "station_id": station_id,
                "month": month,
                "mean": round(fmean(values), 1),
                "n_days": len(values),
            }
        )
    return monthly


def _records(path: Path) -> list[dict]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text())
    if isinstance(payload, dict):
        return list(payload.get("data") or payload.get("stations") or [])
    return list(payload)


def _coordinate(value: object) -> float | None:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def load_coordinate_maps(raw_dir: Path) -> tuple[dict[str, tuple[float, float]], dict[str, tuple[float, float]]]:
    """Site id and normalized name to (latitude, longitude)."""
    by_id: dict[str, tuple[float, float]] = {}
    by_name: dict[str, tuple[float, float]] = {}
    for row in _records(raw_dir / "xkdr_delhi_stations.json"):
        lat = _coordinate(row.get("latitude"))
        lon = _coordinate(row.get("longitude"))
        if lat is None or lon is None:
            continue
        site = str(row.get("station_id") or "").removeprefix("site_")
        if site:
            by_id[site] = (lat, lon)
        name = row.get("station_name") or row.get("name")
        if name:
            by_name.setdefault(normalize_name(str(name)), (lat, lon))
    for row in _records(raw_dir / "cpcb_delhi_realtime_2026-11-22.json"):
        lat = _coordinate(row.get("latitude"))
        lon = _coordinate(row.get("longitude"))
        name = row.get("station")
        if lat is None or lon is None or not name:
            continue
        by_name.setdefault(normalize_name(str(name)), (lat, lon))
    return by_id, by_name


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n")


def _format_aqi(value: float) -> str:
    return format(value, "g")


def build_extract(source_dir: Path, output_dir: Path, raw_dir: Path) -> dict[str, Any]:
    """Read every workbook and write stations, hourly, daily, and monthly files."""
    paths = list(source_dir.glob("*.xlsx"))
    chosen, skipped_duplicates = choose_workbooks(paths)
    by_id, by_name = load_coordinate_maps(raw_dir)
    hours: dict[str, dict[datetime, float]] = defaultdict(dict)
    names: dict[str, tuple[str, str]] = {}
    rejected = 0
    unparsed: list[str] = []
    errors: list[str] = []
    used = 0
    for path in chosen:
        if _FILENAME.match(path.stem) is None:
            unparsed.append(path.name)
            continue
        try:
            sheet = read_workbook(path)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{path.name}: {exc}")
            continue
        used += 1
        rejected += sheet.rejected
        names[sheet.site_id] = (sheet.name, sheet.agency)
        hours[sheet.site_id].update(sheet.hours)

    output_dir.mkdir(parents=True, exist_ok=True)
    hourly_dir = output_dir / "hourly"
    hourly_dir.mkdir(parents=True, exist_ok=True)
    stations = []
    daily: list[dict] = []
    located = 0
    for site_id in sorted(names, key=int):
        station_id = f"site_{site_id}"
        name, agency = names[site_id]
        point = by_id.get(site_id) or by_name.get(normalize_name(name))
        latitude = longitude = None
        if point is not None:
            latitude, longitude = point
            located += 1
        stations.append(
            {
                "station_id": station_id,
                "site_id": site_id,
                "name": name,
                "agency": agency,
                "latitude": latitude,
                "longitude": longitude,
            }
        )
        series = hours[site_id]
        with gzip.open(hourly_dir / f"{site_id}.csv.gz", "wt", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["observed_at", "aqi"])
            for stamp, value in sorted(series.items()):
                writer.writerow([stamp.isoformat(timespec="seconds"), _format_aqi(value)])
        daily.extend(daily_from_hours(station_id, series))

    daily.sort(key=lambda row: (row["station_id"], row["day"]))
    monthly = monthly_from_daily(daily)
    days = [row["day"] for row in daily]
    payload_head = {
        "source": SOURCE,
        "value_kind": VALUE_KIND,
        "timezone": TIMEZONE_NAME,
        "min_hours": MIN_HOURS,
    }
    _write_json(
        output_dir / "stations.json",
        {
            **payload_head,
            "coverage_start": min(days) if days else None,
            "coverage_end": max(days) if days else None,
            "stations": stations,
        },
    )
    _write_json(output_dir / "daily.json", {**payload_head, "data": daily})
    _write_json(output_dir / "monthly.json", {**payload_head, "data": monthly})
    return {
        "files": used,
        "skipped_duplicates": skipped_duplicates,
        "unparsed": unparsed,
        "errors": errors[:20],
        "stations": len(stations),
        "stations_with_coordinates": located,
        "hours": sum(len(series) for series in hours.values()),
        "rejected": rejected,
        "daily_rows": len(daily),
        "monthly_rows": len(monthly),
        "output": str(output_dir),
    }


def load_cpcb_stations(processed_dir: Path) -> list[dict]:
    stations = []
    for row in _records(processed_dir / "stations.json"):
        latitude = _coordinate(row.get("latitude"))
        longitude = _coordinate(row.get("longitude"))
        stations.append(
            {
                "station_id": row["station_id"],
                "site_id": str(row.get("site_id") or row["station_id"].removeprefix("site_")),
                "name": row.get("name") or row["station_id"],
                "agency": row.get("agency"),
                "latitude": latitude,
                "longitude": longitude,
            }
        )
    return stations


def load_daily_rows(processed_dir: Path) -> list[dict]:
    return _records(processed_dir / "daily.json")


def year_labels(year: int) -> dict[str, Any]:
    """Which AQI definition a year uses, and whether the year is incomplete."""
    hourly = year >= HOURLY_AQI_FROM_YEAR
    partial = year == PARTIAL_YEAR
    return {
        "aqi_source": "cpcb_hourly_index" if hourly else "concentration_subindex",
        "partial": partial,
        "coverage_end": COVERAGE_END if partial else None,
        "coverage_note": COVERAGE_NOTE if partial else None,
    }


def hourly_station_years(processed_dir: Path, year: int) -> dict[str, dict]:
    """Annual means from the processed hourly AQI extract, with the partial-year note."""
    annual = annual_index(processed_dir, year)
    note = year_labels(year)["coverage_note"]
    if note:
        for record in annual.values():
            record["coverage_note"] = note
    return annual


def annual_index(processed_dir: Path, year: int, min_days: int = MIN_DAYS) -> dict[str, dict]:
    """Mean daily AQI for one year, for stations with enough valid days."""
    prefix = f"{year}-"
    grouped: dict[str, dict[str, float]] = defaultdict(dict)
    for row in load_daily_rows(processed_dir):
        day = str(row.get("day") or "")
        if row.get("mean") is None or not day.startswith(prefix):
            continue
        grouped[row["station_id"]][day] = float(row["mean"])
    return annual_from_daily(grouped, min_days)


def _station_index(processed_dir: Path) -> dict[str, dict]:
    return {row["station_id"]: row for row in load_cpcb_stations(processed_dir)}


def _in_span(token: str, start: date | None, end: date | None) -> bool:
    if start is not None and token < start.isoformat()[: len(token)]:
        return False
    if end is not None and token > end.isoformat()[: len(token)]:
        return False
    return True


def _slice(rows: list[dict], offset: int, limit: int) -> dict[str, Any]:
    selected = rows[offset : offset + limit]
    return {
        "count": len(selected),
        "matched": len(rows),
        "offset": offset,
        "limit": limit,
        "truncated": offset + len(selected) < len(rows),
        "rows": selected,
    }


def query_series(
    processed_dir: Path,
    *,
    station_id: str | None = None,
    start: date | None = None,
    end: date | None = None,
    aggregation: str = "day",
    offset: int = 0,
    limit: int = 1000,
) -> dict[str, Any]:
    """Filter the stored hourly, daily, or monthly AQI index."""
    wanted = canonical_station_id(station_id) if station_id else None
    stations = _station_index(processed_dir)
    names = {key: row["name"] for key, row in stations.items()}
    base = {
        "source": SOURCE,
        "value_kind": VALUE_KIND,
        "data_kind": "observed",
        "aggregation": aggregation,
        "unit": "index",
        "timezone": TIMEZONE_NAME,
    }
    if wanted is not None and wanted not in stations:
        return {**base, "note": f"Unknown station {station_id}.", **_slice([], offset, limit)}

    if aggregation == "hour":
        files = []
        hourly_dir = processed_dir / "hourly"
        if wanted is not None:
            files = [hourly_dir / f"{wanted.removeprefix('site_')}.csv.gz"]
        elif hourly_dir.exists():
            files = sorted(hourly_dir.glob("*.csv.gz"), key=lambda path: int(path.name.split(".", 1)[0]))
        rows = []
        for path in files:
            if not path.exists():
                continue
            site = path.name.removesuffix(".csv.gz")
            station = f"site_{site}"
            with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
                for record in csv.DictReader(handle):
                    observed = record["observed_at"]
                    if not _in_span(observed[:10], start, end):
                        continue
                    rows.append(
                        {
                            "station_id": station,
                            "name": names.get(station, station),
                            "observed_at": observed,
                            "aqi": float(record["aqi"]),
                        }
                    )
        rows.sort(key=lambda row: (row["observed_at"], row["station_id"]))
        note = "CPCB published hourly AQI index. Blank hours are omitted. This is not a concentration."
    elif aggregation == "month":
        rows = []
        for record in _records(processed_dir / "monthly.json"):
            if wanted is not None and record["station_id"] != wanted:
                continue
            if not _in_span(str(record["month"]), start, end):
                continue
            rows.append(
                {
                    "station_id": record["station_id"],
                    "name": names.get(record["station_id"], record["station_id"]),
                    "month": record["month"],
                    "mean": record["mean"],
                    "n_days": record["n_days"],
                }
            )
        rows.sort(key=lambda row: (row["month"], row["station_id"]))
        note = "Mean of daily AQI means. A day counts only when it has 16 or more hourly values."
    else:
        rows = []
        for record in load_daily_rows(processed_dir):
            if wanted is not None and record["station_id"] != wanted:
                continue
            if not _in_span(str(record["day"]), start, end):
                continue
            rows.append(
                {
                    "station_id": record["station_id"],
                    "name": names.get(record["station_id"], record["station_id"]),
                    "day": record["day"],
                    "mean": record["mean"],
                    "max": record["max"],
                    "n": record["n"],
                }
            )
        rows.sort(key=lambda row: (row["day"], row["station_id"]))
        note = "Daily mean and maximum of CPCB hourly AQI. Days with fewer than 16 hours are omitted."
    return {**base, "note": note, **_slice(rows, offset, limit)}
