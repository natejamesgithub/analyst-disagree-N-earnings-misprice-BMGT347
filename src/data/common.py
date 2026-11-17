"""Canonical CSV contracts and command-line utilities."""

import argparse
import csv
from dataclasses import dataclass
from datetime import date
import gzip
from pathlib import Path
import tomllib

import numpy as np
import pandas as pd


class DataError(ValueError):
    """An actionable input or configuration error."""


@dataclass(frozen=True)
class Study:
    start: date
    end: date
    forecast_days: int
    min_analysts: int
    consensus_floor: float
    max_ibes_score: int
    unknown_time: str
    crsp_format: str
    fundamentals: str
    fundamentals_lag_days: int
    max_fundamentals_age: int

    @classmethod
    def load(cls, path):
        with path.open("rb") as stream:
            try:
                study = cls(**tomllib.load(stream)["study"])
            except (KeyError, TypeError, ValueError) as exc:
                raise DataError(f"{path}: invalid [study] settings: {exc}") from exc
        if type(study.start) is not date or type(study.end) is not date or study.start > study.end:
            raise DataError("Use ordered TOML dates for start and end")
        for name, lower, upper in (
            ("forecast_days", 1, 366),
            ("min_analysts", 2, 10000),
            ("max_ibes_score", 0, 6),
            ("fundamentals_lag_days", 0, 730),
            ("max_fundamentals_age", 1, 1500),
        ):
            value = getattr(study, name)
            if type(value) is not int or not lower <= value <= upper:
                raise DataError(f"{name} must be an integer in [{lower}, {upper}]")
        floor = study.consensus_floor
        if type(floor) not in (int, float) or not np.isfinite(floor) or floor <= 0:
            raise DataError("consensus_floor must be finite and positive")
        for name, choices in (
            ("unknown_time", ("exclude", "next_session")),
            ("crsp_format", ("ciz", "legacy")),
            ("fundamentals", ("rdq", "vintage")),
        ):
            if getattr(study, name) not in choices:
                raise DataError(f"{name} must be one of {choices}")
        return study


def read_csv(directory, name, columns, optional=()):
    """Read only contracted fields, preserving identifiers and leading zeros."""
    path = directory / f"{name}.csv"
    if not path.is_file():
        path = directory / f"{name}.csv.gz"
    try:
        opener = gzip.open if path.suffix == ".gz" else open
        with opener(path, "rt", encoding="utf-8-sig", newline="") as stream:
            header = next(csv.reader(stream, strict=True), [])
        normalized = [column.strip().lower() for column in header]
        if len(normalized) != len(set(normalized)):
            raise DataError("duplicate column names")
        missing = set(columns) - set(normalized)
        if missing:
            raise DataError(f"missing columns {', '.join(sorted(missing))}")
        wanted = set(columns) | set(optional)
        frame = pd.read_csv(
            path, usecols=lambda col: col.strip().lower() in wanted,
            dtype="string", keep_default_na=False, encoding="utf-8-sig",
        )
    except (OSError, ValueError, csv.Error) as exc:
        raise DataError(f"{path}: {exc}") from exc
    frame.columns = frame.columns.str.strip().str.lower()
    for column in frame:
        values = frame[column].str.strip()
        frame[column] = values.mask(values.isin(["", ".", "NULL", "NaN", "<NA>"]))
    for column in optional:
        if column not in frame:
            frame[column] = pd.Series(pd.NA, index=frame.index, dtype="string")
    return frame


def validate(frame, source, column, valid):
    if not valid.fillna(False).all():
        rows = (frame.index[~valid.fillna(False)][:5] + 2).tolist()
        raise DataError(f"{source}.{column}: invalid values at CSV lines {rows}")


def identifiers(frame, source, columns):
    for column in columns:
        validate(frame, source, column, frame[column].notna())


def dates(frame, source, column, nullable=False):
    values = frame[column]
    parsed = pd.to_datetime(values, format="%Y-%m-%d", errors="coerce")
    valid = parsed.notna() & values.str.fullmatch(r"\d{4}-\d{2}-\d{2}")
    validate(frame, source, column, valid | (nullable & values.isna()))
    frame[column] = parsed


def numbers(frame, source, column, nullable=False, minimum=None, integer=False):
    values = frame[column]
    parsed = pd.to_numeric(values, errors="coerce").astype("float64")
    valid = pd.Series(np.isfinite(parsed), index=frame.index)
    if minimum is not None:
        valid &= parsed.ge(minimum)
    if integer:
        valid &= parsed.mod(1).eq(0) & parsed.abs().lt(2**53)
    validate(frame, source, column, valid | (nullable & values.isna()))
    frame[column] = parsed.astype("Int64") if integer else parsed


def clock_seconds(frame, source, column, nullable=False):
    values = frame[column]
    valid = values.str.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d(?::[0-5]\d)?")
    validate(frame, source, column, valid | (nullable & values.isna()))
    parts = values.str.split(":")
    frame[column] = (
        pd.to_numeric(parts.str[0]).astype(float) * 3600
        + pd.to_numeric(parts.str[1]).astype(float) * 60
        + pd.to_numeric(parts.str[2]).astype(float).fillna(0)
    )


def unique(frame, source, keys):
    frame = frame.drop_duplicates()
    duplicates = frame.duplicated(keys, keep=False)
    if duplicates.any():
        raise DataError(f"{source}: {duplicates.sum()} conflicting rows for key {keys}")
    return frame


def intervals(frame, source, start, end):
    dates(frame, source, start, nullable=True)
    dates(frame, source, end, nullable=True)
    validate(frame, source, end, frame[start].isna() | frame[end].isna() | frame[start].le(frame[end]))


def parser(description, cleaned=False):
    cli = argparse.ArgumentParser(description=description)
    cli.add_argument("--input-dir", type=Path, required=True)
    cli.add_argument("--output-dir", type=Path, required=True)
    cli.add_argument("--config", type=Path, default=Path("config.toml"))
    if cleaned:
        cli.add_argument("--clean-dir", type=Path)
    return cli


def main_for(loader, description):
    cli = parser(description)
    args = cli.parse_args()
    try:
        from .storage import publish

        tables = loader(args.input_dir, Study.load(args.config))
        publish(args.output_dir, tables)
    except (OSError, ValueError) as exc:
        cli.exit(2, f"error: {exc}\n")
