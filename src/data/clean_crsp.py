"""Validate CRSP security returns, historical metadata and the market calendar."""

import numpy as np

from .common import (
    DataError, clock_seconds, dates, intervals, main_for, numbers, read_csv, unique, validate,
)

DAILY = ("permno", "date", "ret", "prc", "shrout", "cfacpr")
MARKET = ("date", "vwretd", "close_time")
NAMES = ("permno", "namedt", "nameendt", "shrcd", "exchcd")


def load(directory, study):
    optional = ("dlret",) if study.crsp_format == "ciz" else ()
    required = DAILY + (("dlret",) if study.crsp_format == "legacy" else ())
    daily = read_csv(directory, "crsp_daily", required, optional)
    market = read_csv(directory, "crsp_market", MARKET)
    names = read_csv(directory, "crsp_names", NAMES)

    numbers(daily, "crsp_daily", "permno", minimum=1, integer=True)
    dates(daily, "crsp_daily", "date")
    for column in ("ret", "dlret"):
        numbers(daily, "crsp_daily", column, nullable=True, minimum=-1)
    if study.crsp_format == "ciz" and daily["dlret"].notna().any():
        raise DataError("crsp_daily.dlret: CIZ uses the supplied total return; remove dlret")
    numbers(daily, "crsp_daily", "prc", nullable=True)
    daily["prc"] = daily["prc"].abs().replace(0, np.nan)
    for column in ("shrout", "cfacpr"):
        numbers(daily, "crsp_daily", column, nullable=True, minimum=0)
        daily[column] = daily[column].replace(0, np.nan)
    daily = unique(daily, "crsp_daily", ["permno", "date"])
    daily["total_return"] = daily["ret"]
    has_delist = daily["dlret"].notna()
    daily.loc[has_delist, "total_return"] = (
        (1 + daily.loc[has_delist, "ret"].fillna(0))
        * (1 + daily.loc[has_delist, "dlret"]) - 1
    )

    dates(market, "crsp_market", "date")
    numbers(market, "crsp_market", "vwretd", minimum=-1)
    timing = market.copy()
    clock_seconds(timing, "crsp_market", "close_time")
    market["close_seconds"] = timing["close_time"]
    market = unique(market, "crsp_market", ["date"]).sort_values("date")
    if market.empty:
        raise DataError("crsp_market must contain at least one trading session")
    validate(daily, "crsp_daily", "date", daily["date"].isin(market["date"]))

    for column in ("permno", "shrcd", "exchcd"):
        numbers(names, "crsp_names", column, integer=True, minimum=1 if column == "permno" else None)
    intervals(names, "crsp_names", "namedt", "nameendt")
    validate(names, "crsp_names", "namedt", names["namedt"].notna())
    return daily, market, names.drop_duplicates()


def clean(directory, study):
    daily, market, names = load(directory, study)
    columns = DAILY + (("dlret",) if study.crsp_format == "legacy" else ())
    return {
        "crsp_daily": daily.loc[:, list(columns)],
        "crsp_market": market.loc[:, list(MARKET)],
        "crsp_names": names.loc[:, list(NAMES)],
    }


if __name__ == "__main__":
    main_for(clean, __doc__)
