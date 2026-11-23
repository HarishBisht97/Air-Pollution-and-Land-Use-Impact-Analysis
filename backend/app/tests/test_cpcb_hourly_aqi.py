import json
import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path

from app.ingestion.cpcb_hourly_aqi import (
    COVERAGE_END,
    IST,
    build_extract,
    choose_workbooks,
    daily_from_hours,
    hourly_station_years,
    query_series,
    read_workbook,
    year_labels,
)

_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"


def _cell(ref: str, value: str | None, numeric: bool) -> str:
    if value is None:
        return f'<c r="{ref}" t="inlineStr"></c>'
    if numeric:
        return f'<c r="{ref}" t="n"><v>{value}</v></c>'
    return f'<c r="{ref}" t="inlineStr"><is><t>{value}</t></is></c>'


def _write_matrix(path: Path, rows: list[list[str | None]]) -> None:
    body = []
    for row_number, values in enumerate(rows, start=1):
        cells = []
        for column, value in enumerate(values):
            letters = chr(ord("A") + column)
            numeric = value is not None and value.replace(".", "", 1).isdigit()
            cells.append(_cell(f"{letters}{row_number}", value, numeric))
        body.append(f'<row r="{row_number}">{"".join(cells)}</row>')
    xml = (
        f'<worksheet xmlns="{_NS}"><sheetData>{"".join(body)}</sheetData></worksheet>'
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("xl/worksheets/sheet1.xml", xml)


def _january_name(suffix: str = "") -> str:
    return (
        "AQI_Data_Station_Level_Site_103_CRRI_Mathura_Road_Delhi_IITM_"
        f"January_2025_Hourly{suffix}.xlsx"
    )


def test_blank_hours_dropped_and_out_of_range_rejected(tmp_path: Path):
    header = ["Date", *[f"{hour:02d}:00" for hour in range(24)]]
    full = ["1", *["100"] * 15, None, "900", *["110"] * 7]
    short = ["2", *["50"] * 10, *([None] * 14)]
    path = tmp_path / _january_name()
    _write_matrix(path, [header, full, short])

    sheet = read_workbook(path)
    assert sheet.rejected == 1
    assert sum(1 for stamp in sheet.hours if stamp.day == 1) == 22
    assert sum(1 for stamp in sheet.hours if stamp.day == 2) == 10
    assert datetime(2025, 1, 1, 15, tzinfo=IST) not in sheet.hours
    assert all(value <= 500 for value in sheet.hours.values())

    daily = daily_from_hours("site_103", sheet.hours)
    assert [row["day"] for row in daily] == ["2025-01-01"]
    assert daily[0]["n"] == 22
    assert daily[0]["max"] == 110


def test_duplicate_download_is_ignored():
    canonical = Path(_january_name())
    copy = Path(_january_name(" (1)"))
    kept, skipped = choose_workbooks([copy, canonical])
    assert skipped == 1
    assert kept == [canonical]


def test_extract_skips_duplicate_and_uses_coordinates(tmp_path: Path):
    source = tmp_path / "xlsx"
    raw = tmp_path / "raw"
    output = tmp_path / "processed"
    raw.mkdir()
    header = ["Date", *[f"{hour:02d}:00" for hour in range(24)]]
    day = ["1", *["80"] * 16, *([None] * 8)]
    _write_matrix(source / _january_name(), [header, day])
    _write_matrix(source / _january_name(" (1)"), [header, ["1", *["10"] * 24]])
    (raw / "xkdr_delhi_stations.json").write_text(
        json.dumps(
            {
                "data": [
                    {
                        "station_id": "site_103",
                        "station_name": "CRRI Mathura Road, Delhi - IMD",
                        "latitude": 28.5512,
                        "longitude": 77.2736,
                    }
                ]
            }
        )
    )

    report = build_extract(source, output, raw)
    assert report["skipped_duplicates"] == 1
    assert report["files"] == 1
    assert report["stations_with_coordinates"] == 1
    assert report["daily_rows"] == 1
    stations = json.loads((output / "stations.json").read_text())["stations"]
    assert stations[0]["station_id"] == "site_103"
    assert stations[0]["latitude"] == 28.5512
    daily = json.loads((output / "daily.json").read_text())["data"]
    assert daily[0]["mean"] == 80
    assert daily[0]["n"] == 16

    result = query_series(output, station_id="103", aggregation="day")
    assert result["value_kind"] == "aqi_index"
    assert result["source"] == "CPCB CCR station hourly AQI"
    assert result["data_kind"] == "observed"
    assert result["rows"][0]["day"] == "2025-01-01"
    assert result["rows"][0]["name"] == "CRRI Mathura Road"


def test_hourly_query_filters_station_and_date(tmp_path: Path):
    source = tmp_path / "xlsx"
    raw = tmp_path / "raw"
    output = tmp_path / "processed"
    raw.mkdir()
    (raw / "xkdr_delhi_stations.json").write_text(json.dumps({"data": []}))
    (raw / "cpcb_delhi_realtime_2026-11-22.json").write_text(
        json.dumps(
            [
                {
                    "station": "IIT Delhi, Delhi - IITM",
                    "latitude": 28.54246,
                    "longitude": 77.191651,
                }
            ]
        )
    )
    header = ["Date", *[f"{hour:02d}:00" for hour in range(24)]]
    day = ["4", *["120"] * 18, *([None] * 6)]
    name = "AQI_Data_Station_Level_Site_6060_IIT_Delhi_Delhi_IITM_October_2026_Hourly.xlsx"
    _write_matrix(source / name, [header, day])

    report = build_extract(source, output, raw)
    assert report["stations_with_coordinates"] == 1
    hourly = query_series(
        output,
        station_id="site_6060",
        aggregation="hour",
        start=date(2026, 10, 4),
        end=date(2026, 10, 4),
    )
    assert hourly["matched"] == 18
    assert hourly["rows"][0]["observed_at"].startswith("2026-10-04T00:00:00+05:30")
    monthly = query_series(output, aggregation="month")
    assert monthly["rows"][0]["month"] == "2026-10"
    assert monthly["rows"][0]["n_days"] == 1
    assert COVERAGE_END == "2026-10-31"


def test_2025_reads_processed_daily_and_2026_is_partial(tmp_path: Path):
    rows = []
    for year, value in ((2025, 120.0), (2026, 80.0)):
        for offset in range(180):
            day = date(year, 1, 1) + timedelta(days=offset)
            rows.append({"station_id": "site_103", "day": day.isoformat(), "mean": value, "max": value, "n": 20})
    rows.append({"station_id": "site_104", "day": "2025-01-01", "mean": 300.0, "max": 300.0, "n": 20})
    (tmp_path / "daily.json").write_text(json.dumps({"data": rows}))

    year_2025 = hourly_station_years(tmp_path, 2025)
    year_2026 = hourly_station_years(tmp_path, 2026)
    assert year_2025["site_103"]["aqi"] == 120.0
    assert "coverage_note" not in year_2025["site_103"]
    assert "site_104" not in year_2025
    assert year_2026["site_103"]["aqi"] == 80.0
    assert "October" in year_2026["site_103"]["coverage_note"]
    assert year_labels(2024)["aqi_source"] == "concentration_subindex"
    assert year_labels(2024)["partial"] is False
    assert year_labels(2025)["aqi_source"] == "cpcb_hourly_index"
    assert year_labels(2025)["partial"] is False
    assert year_labels(2026)["partial"] is True
    assert year_labels(2026)["coverage_end"] == "2026-10-31"
