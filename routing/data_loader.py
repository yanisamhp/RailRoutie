"""Shared loader for the Dai routing handoff dataset (``dai_routing_v2``).

The dataset is master data and is treated as **read-only**: this module only
reads the four CSV files and never writes to the data folder.

All CSV files carry a UTF-8 BOM, so they are always read with
``encoding="utf-8-sig"``.

The data directory can be supplied explicitly, via the environment variable
``DAI_ROUTING_DATA_DIR``, or falls back to ``../../dai_routing_v2`` relative to
this file (``DSI463_v3/dai_routing_v2``).
"""

from __future__ import annotations

import csv
import math
import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Optional, Union

PathLike = Union[str, Path]

DEFAULT_DATA_DIR: Path = (Path(__file__).resolve().parent / ".." / ".." / "dai_routing_v2").resolve()
DATA_DIR_ENV = "DAI_ROUTING_DATA_DIR"

STATIONS_FILE = "stations_coordinates_provisional.csv"
LINES_FILE = "lines_master.csv"
RIDE_EDGES_FILE = "ride_edges_master.csv"
INTERCHANGES_FILE = "interchanges_master.csv"
CSV_ENCODING = "utf-8-sig"


class DataIntegrityError(ValueError):
    """Raised when the dataset violates a referential-integrity rule."""


@dataclass(frozen=True)
class Station:
    """One station-line record. Key = ``station_line_id`` (never station_code or name)."""

    station_line_id: str
    station_id: str
    line_id: str
    station_code: str
    seq: Optional[int]
    name_en: str
    name_th: str
    latitude: float
    longitude: float
    coordinate_origin: str
    coordinate_qa_status: str
    osm_reference_url: str


@dataclass(frozen=True)
class Line:
    """One rail line from ``lines_master.csv``."""

    line_id: str
    name_en: str
    name_th: str
    operator: str
    color_hex: str
    branch_from: str


@dataclass(frozen=True)
class RideEdge:
    """A RIDE connection between two consecutive stations of the same line."""

    edge_id: str
    line_id: str
    source: str
    target: str
    edge_type: str
    stops: int


@dataclass(frozen=True)
class Interchange:
    """A TRANSFER or BRANCH_JUNCTION connection between two station-line records."""

    connection_id: str
    station_line_id_a: str
    station_line_id_b: str
    connection_category: str
    distance_m_from_file: Optional[float]
    transfer_type: str


@dataclass
class Dataset:
    """In-memory view of the four handoff CSV files."""

    data_dir: Path
    stations: dict[str, Station] = field(default_factory=dict)
    lines: dict[str, Line] = field(default_factory=dict)
    ride_edges: list[RideEdge] = field(default_factory=list)
    interchanges: list[Interchange] = field(default_factory=list)

    def line_name_th(self, line_id: str) -> Optional[str]:
        """Return the Thai line name, or ``None`` if the line is unknown."""
        line = self.lines.get(line_id)
        return line.name_th if line else None

    def has_station(self, station_line_id: str) -> bool:
        """True if ``station_line_id`` exists in the dataset."""
        return station_line_id in self.stations


def resolve_data_dir(data_dir: Optional[PathLike] = None) -> Path:
    """Resolve the dataset directory (argument > env var > default relative path)."""
    if data_dir is not None:
        return Path(data_dir).expanduser().resolve()
    env = os.environ.get(DATA_DIR_ENV)
    if env:
        return Path(env).expanduser().resolve()
    return DEFAULT_DATA_DIR


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(f"Dataset file not found: {path}")
    with path.open("r", encoding=CSV_ENCODING, newline="") as fh:
        return [{k.strip(): (v or "").strip() for k, v in row.items()} for row in csv.DictReader(fh)]


def _opt_float(value: str) -> Optional[float]:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) else f


def _opt_int(value: str) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _load(data_dir: Path) -> Dataset:
    ds = Dataset(data_dir=data_dir)

    for row in _read_csv(data_dir / LINES_FILE):
        ds.lines[row["line_id"]] = Line(
            line_id=row["line_id"],
            name_en=row.get("name_en", ""),
            name_th=row.get("name_th", ""),
            operator=row.get("operator", ""),
            color_hex=row.get("color_hex", ""),
            branch_from=row.get("branch_from", ""),
        )

    for row in _read_csv(data_dir / STATIONS_FILE):
        sid = row["station_line_id"]
        lat, lon = _opt_float(row.get("latitude", "")), _opt_float(row.get("longitude", ""))
        if lat is None or lon is None:
            raise DataIntegrityError(f"Station {sid} has no usable coordinates")
        if sid in ds.stations:
            raise DataIntegrityError(f"Duplicate station_line_id: {sid}")
        ds.stations[sid] = Station(
            station_line_id=sid,
            station_id=row.get("station_id", ""),
            line_id=row["line_id"],
            station_code=row.get("station_code", ""),
            seq=_opt_int(row.get("seq", "")),
            name_en=row.get("name_en", ""),
            name_th=row.get("name_th", ""),
            latitude=lat,
            longitude=lon,
            coordinate_origin=row.get("coordinate_origin", ""),
            coordinate_qa_status=row.get("coordinate_qa_status", ""),
            osm_reference_url=row.get("osm_reference_url", ""),
        )

    for row in _read_csv(data_dir / RIDE_EDGES_FILE):
        ds.ride_edges.append(
            RideEdge(
                edge_id=row["edge_id"],
                line_id=row["line_id"],
                source=row["source_station_line_id"],
                target=row["target_station_line_id"],
                edge_type=row.get("edge_type", "RIDE") or "RIDE",
                stops=_opt_int(row.get("stops", "1")) or 1,
            )
        )

    for row in _read_csv(data_dir / INTERCHANGES_FILE):
        ds.interchanges.append(
            Interchange(
                connection_id=row["connection_id"],
                station_line_id_a=row["station_line_id_a"],
                station_line_id_b=row["station_line_id_b"],
                connection_category=row["connection_category"],
                distance_m_from_file=_opt_float(row.get("distance_m_from_file", "")),
                transfer_type=row.get("transfer_type", ""),
            )
        )

    issues = validate_dataset(ds)
    if issues:
        raise DataIntegrityError("; ".join(issues))
    return ds


def validate_dataset(ds: Dataset) -> list[str]:
    """Return a list of referential-integrity problems (empty list = OK)."""
    issues: list[str] = []
    for st in ds.stations.values():
        if st.line_id not in ds.lines:
            issues.append(f"station {st.station_line_id}: unknown line_id {st.line_id}")
    for e in ds.ride_edges:
        for end in (e.source, e.target):
            if end not in ds.stations:
                issues.append(f"{e.edge_id}: unknown station {end}")
        if e.line_id not in ds.lines:
            issues.append(f"{e.edge_id}: unknown line_id {e.line_id}")
    for c in ds.interchanges:
        for end in (c.station_line_id_a, c.station_line_id_b):
            if end not in ds.stations:
                issues.append(f"{c.connection_id}: unknown station {end}")
        if c.connection_category not in ("TRANSFER", "BRANCH_JUNCTION"):
            issues.append(f"{c.connection_id}: unexpected category {c.connection_category}")
    return issues


@lru_cache(maxsize=8)
def _load_cached(data_dir: str) -> Dataset:
    return _load(Path(data_dir))


def load_dataset(data_dir: Optional[PathLike] = None) -> Dataset:
    """Load (and cache per directory) the routing dataset.

    Args:
        data_dir: Folder containing the four CSV files. ``None`` uses
            ``$DAI_ROUTING_DATA_DIR`` or ``../../dai_routing_v2`` relative to this file.

    Raises:
        FileNotFoundError: a CSV file is missing.
        DataIntegrityError: orphan IDs or other integrity problems.
    """
    return _load_cached(str(resolve_data_dir(data_dir)))
