"""Validate quarterly USD I/B/E/S Detail and Actuals exports."""

from .common import (
    clock_seconds, dates, identifiers, main_for, numbers, read_csv, validate,
)

FORECASTS = (
    "ticker", "fpedats", "estimator", "analys", "anndats", "actdats", "value",
    "measure", "fpi", "curr",
)
ACTUALS = ("ticker", "pends", "anndats", "value", "measure", "pdicity", "curr")
FORECAST_OPTIONAL = ("pdf",)
ACTUAL_OPTIONAL = ("anntims", "eps_basis")


def load(directory, study):
    forecasts = read_csv(directory, "ibes_forecasts", FORECASTS, FORECAST_OPTIONAL)
    actuals = read_csv(directory, "ibes_actuals", ACTUALS, ACTUAL_OPTIONAL)
    for frame, source, period, frequency, accepted in (
        (forecasts, "ibes_forecasts", "fpedats", "fpi", ("6", "7", "8", "9", "N", "O", "P", "Q", "Y")),
        (actuals, "ibes_actuals", "pends", "pdicity", ("QTR",)),
    ):
        for column, allowed in (
            ("measure", ("EPS",)), ("curr", ("USD",)), (frequency, accepted),
        ):
            validate(frame, source, column, frame[column].str.upper().isin(allowed))
        identifiers(frame, source, ("ticker",))
        frame["ticker"] = frame["ticker"].str.upper()
        dates(frame, source, period)
        dates(frame, source, "anndats")
        numbers(frame, source, "value", nullable=True)

    for frame, source, column in (
        (forecasts, "ibes_forecasts", "pdf"), (actuals, "ibes_actuals", "eps_basis"),
    ):
        frame[column] = frame[column].str.upper()
        validate(frame, source, column, frame[column].isna() | frame[column].isin(["P", "D"]))

    dates(forecasts, "ibes_forecasts", "actdats", nullable=True)
    validate(
        forecasts, "ibes_forecasts", "actdats",
        forecasts["actdats"].isna() | forecasts["actdats"].ge(forecasts["anndats"]),
    )
    timing = actuals.copy()
    clock_seconds(timing, "ibes_actuals", "anntims", nullable=True)
    actuals["ann_seconds"] = timing["anntims"]
    validate(actuals, "ibes_actuals", "anndats", actuals["anndats"].ge(actuals["pends"]))
    return forecasts.drop_duplicates(), actuals.drop_duplicates()


def clean(directory, study):
    forecasts, actuals = load(directory, study)
    return {
        "ibes_forecasts": forecasts.loc[:, list(FORECASTS + FORECAST_OPTIONAL)],
        "ibes_actuals": actuals.loc[:, list(ACTUALS + ACTUAL_OPTIONAL)],
    }


if __name__ == "__main__":
    main_for(clean, __doc__)
