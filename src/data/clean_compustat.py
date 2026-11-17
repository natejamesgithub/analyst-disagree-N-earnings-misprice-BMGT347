"""Validate quarterly Compustat book equity and its availability dates."""

import pandas as pd

from .common import dates, identifiers, main_for, numbers, read_csv, unique, validate

BASE = ("gvkey", "datadate", "ceqq", "curcdq", "indfmt", "datafmt", "popsrc", "consol")


def load(directory, study):
    availability = "rdq" if study.fundamentals == "rdq" else "available_date"
    frame = read_csv(directory, "compustat_quarterly", BASE + (availability,))
    identifiers(frame, "compustat_quarterly", ("gvkey",))
    # Retain leading zeros and normalize short numeric GVKEY exports.
    validate(frame, "compustat_quarterly", "gvkey", frame["gvkey"].str.fullmatch(r"\d{1,6}"))
    frame["gvkey"] = frame["gvkey"].str.zfill(6)
    for column, value in (
        ("curcdq", "USD"), ("indfmt", "INDL"), ("datafmt", "STD"),
        ("popsrc", "D"), ("consol", "C"),
    ):
        validate(frame, "compustat_quarterly", column, frame[column].str.upper().eq(value))
    dates(frame, "compustat_quarterly", "datadate")
    dates(frame, "compustat_quarterly", availability, nullable=True)
    numbers(frame, "compustat_quarterly", "ceqq", nullable=True)
    validate(
        frame, "compustat_quarterly", availability,
        frame[availability].isna() | frame[availability].ge(frame["datadate"]),
    )
    keys = ["gvkey", "datadate"]
    if study.fundamentals == "vintage":
        keys.append(availability)
    frame = unique(frame, "compustat_quarterly", keys).copy()
    frame["known_date"] = frame[availability]
    if study.fundamentals == "rdq":
        floor = frame["datadate"] + pd.Timedelta(days=study.fundamentals_lag_days)
        # Missing RDQ stays missing.
        frame["known_date"] = frame[availability].where(frame[availability].ge(floor), floor)
        frame.loc[frame[availability].isna(), "known_date"] = pd.NaT
    return frame


def clean(directory, study):
    return {"compustat_quarterly": load(directory, study).drop(columns="known_date")}


if __name__ == "__main__":
    main_for(clean, __doc__)
