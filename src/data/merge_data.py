"""Build the event-level panel, sample exclusions and reproducibility audit."""

from collections import Counter
from dataclasses import asdict
import hashlib
import platform

import numpy as np
import pandas as pd

from . import clean_compustat, clean_crsp, clean_ibes, links
from .common import DataError, Study, parser
from .storage import publish

KEY = ["ticker", "pends"]
WINDOWS = {
    "car_m1_p1": (-1, 1),
    "car_p2_p20": (2, 20),
    "car_p2_p60": (2, 60),
}
PANEL_COLUMNS = [
    "ticker", "pends", "announcement_date", "announcement_time", "event_date",
    "timing", "reference_date", "permno", "ibes_link_score", "gvkey", "ccm_status",
    "actual_eps", "actual_eps_basis", "forecast_eps_basis", "consensus_eps", "forecast_std_eps", "analyst_count",
    "last_forecast_date", "last_activation_date", "forecasts_missing_split_basis",
    "forecasts_other_split_basis", "forecasts_unlinked", "forecasts_missing_input",
    "price", "market_cap_millions",
    "log_market_cap", "sue", "abs_sue", "dispersion", "dispersion_price",
    "sue_x_dispersion", "momentum", "volatility", "fundamentals_status",
    "fundamentals_datadate", "fundamentals_known_date", "book_equity_millions",
    "book_to_market", "abret_0",
    *WINDOWS,
]


def grouped(frame, keys):
    return dict(tuple(frame.groupby(keys, sort=False)))


def prepare_actuals(actuals, study):
    # Inspect the original announcement, including records before the sample start.
    earliest = actuals.groupby(KEY)["anndats"].transform("min")
    first = actuals[actuals["anndats"].eq(earliest)]
    first = first[first["anndats"].between(pd.Timestamp(study.start), pd.Timestamp(study.end))]
    for (ticker, pends), rows in first.groupby(KEY, sort=True):
        base = {"ticker": ticker, "pends": pends, "announcement_date": rows["anndats"].iloc[0]}
        values = rows["value"].dropna().unique()
        times = rows["ann_seconds"].dropna().unique()
        eps_bases = rows["eps_basis"].dropna().unique()
        if len(values) > 1 or len(times) > 1 or len(eps_bases) > 1:
            yield base, "conflicting_actual"
        elif len(values) == 0:
            yield base, "missing_actual"
        else:
            time = rows["anntims"].dropna()
            base.update(
                actual_eps=values[0],
                actual_eps_basis=eps_bases[0] if len(eps_bases) else None,
                announcement_time=time.iloc[0] if len(times) else None,
                ann_seconds=times[0] if len(times) else np.nan,
            )
            yield base, None


def event_position(market, when, seconds, policy):
    index = market.index
    pos = index.searchsorted(when)
    if pos == len(index) or when < index[0]:
        return None, "outside_market_calendar"
    if index[pos] != when:
        return pos, "nontrading_day"
    if np.isnan(seconds):
        return (pos + 1, "unknown_next_session") if policy == "next_session" else (
            None, "unknown_announcement_time"
        )
    if seconds >= market["close_seconds"].iloc[pos]:
        return pos + 1, "at_or_after_close"
    return pos, "before_close"


def consensus(rows, when, permno, ticker_links, stock, calendar, basis, eps_basis, study, counts):
    if rows is None:
        return None, "too_few_analysts"
    rows = rows[rows["anndats"].between(
        when - pd.Timedelta(days=study.forecast_days), when, inclusive="left"
    )]
    complete = rows[["estimator", "analys", "value", "actdats"]].notna().all(axis=1)
    counts["forecasts_missing_input"] = int((~complete).sum())
    rows = rows[complete & rows["actdats"].lt(when)]
    if rows.empty:
        return None, "too_few_analysts"

    # Select the latest issue per contributor and break same-day issues by activation
    # date. A still-tied disagreement has no defensible ordering in a date-only export.
    analyst = ["estimator", "analys"]
    rows = rows[rows["anndats"].eq(rows.groupby(analyst)["anndats"].transform("max"))]
    rows = rows[rows["actdats"].eq(rows.groupby(analyst)["actdats"].transform("max"))]
    if eps_basis is not None:
        rows = rows[rows["pdf"].eq(eps_basis).fillna(False)]
    # Without an actual-basis flag, require the retained forecasts to agree.
    if rows.groupby(analyst)[["value", "pdf"]].nunique(dropna=False).gt(1).any().any():
        return None, "conflicting_forecast"
    rows = rows.drop_duplicates(analyst).copy()

    issue_dates = rows["anndats"].unique()
    linked = {day: links.ibes_match(ticker_links, day)[0] == permno for day in issue_dates}
    same_security = rows["anndats"].map(linked)
    counts["forecasts_unlinked"] = int((~same_security).sum())
    rows = rows[same_security]
    positions = calendar.searchsorted(rows["anndats"], side="right") - 1
    issue_basis = stock["cfacpr"].reindex(calendar[positions]).to_numpy()
    issue_basis[positions < 0] = np.nan
    counts["forecasts_missing_split_basis"] = int(np.isnan(issue_basis).sum())
    same_basis = np.isclose(issue_basis, basis, rtol=1e-10, atol=0)
    counts["forecasts_other_split_basis"] = int((~same_basis & np.isfinite(issue_basis)).sum())
    rows = rows[same_basis]
    if rows["pdf"].nunique(dropna=False) > 1:
        return None, "mixed_forecast_eps_basis"
    if len(rows) < study.min_analysts:
        return None, "too_few_analysts"
    return rows, None


def returns_window(stock, market, left, right):
    if left < 0 or right >= len(market):
        return None
    sessions = market.index[left:right + 1]
    values = stock["total_return"].reindex(sessions).to_numpy()
    return values if np.isfinite(values).all() else None


def abnormal(stock, market, left, right):
    returns = returns_window(stock, market, left, right)
    if returns is None:
        return np.nan
    return float((returns - market["vwretd"].iloc[left:right + 1].to_numpy()).sum())


def attach_fundamentals(record, ccm, fundamentals, reference, study):
    gvkey, link_status = links.ccm_match(ccm, reference)
    record.update(gvkey=gvkey, ccm_status=link_status)
    records = fundamentals.get(gvkey)
    record["fundamentals_status"] = "no_eligible_quarter" if gvkey else link_status
    if records is None:
        return
    eligible = records[
        records["known_date"].lt(reference)
        & records["datadate"].ge(reference - pd.Timedelta(days=study.max_fundamentals_age))
    ]
    if eligible.empty:
        return
    quarter = eligible.iloc[-1]  # sorted by fiscal date, then vintage
    equity = quarter["ceqq"]
    record.update(
        fundamentals_datadate=quarter["datadate"],
        fundamentals_known_date=quarter["known_date"],
        book_equity_millions=equity,
        fundamentals_status="matched" if pd.notna(equity) else "missing_book_equity",
    )
    if equity > 0 and record["market_cap_millions"] > 0:
        record["book_to_market"] = equity / record["market_cap_millions"]


def build(study, ibes, crsp, compustat, link_tables):
    forecasts, actuals = ibes
    daily, market, names = crsp
    market = market.set_index("date")
    calendar = market.index
    ibes_links, ccm = link_tables
    by_forecast = grouped(forecasts, ["ticker", "fpedats"])
    by_ibes = grouped(ibes_links, "ticker")
    by_ccm = grouped(ccm, "lpermno")
    by_name = grouped(names, "permno")
    by_fund = grouped(compustat.sort_values(["datadate", "known_date"]), "gvkey")
    by_stock = grouped(daily.set_index("date"), "permno")
    records, rejected = [], []

    def evaluate(base):
        when = base["announcement_date"]
        pos, timing = event_position(market, when, base["ann_seconds"], study.unknown_time)
        if pos is None:
            return timing
        if pos >= len(market):
            return "outside_market_calendar"
        first_session = calendar.searchsorted(when)
        ref = first_session - 1
        if ref < 0:
            return "missing_reference_session"
        reference = calendar[ref]
        ticker_links = by_ibes.get(base["ticker"])
        permno, score, reason = links.ibes_match(ticker_links, when)
        if permno is None:
            return reason
        base.update(permno=permno, event_date=calendar[pos], timing=timing, reference_date=reference)
        reference_permno, _, reason = links.ibes_match(ticker_links, reference)
        if reference_permno != permno:
            return "ambiguous_reference_ibes_link" if reason == "ambiguous_ibes_link" else "unstable_ibes_link"
        metadata = by_name.get(permno)
        if metadata is None:
            return "missing_security_metadata"
        current = links.active(metadata, reference, "namedt", "nameendt")
        codes = current[["shrcd", "exchcd"]].drop_duplicates()
        if codes.empty:
            return "missing_security_metadata"
        if len(codes) > 1:
            return "ambiguous_security_metadata"
        share, exchange = codes.iloc[0]
        if share not in (10, 11) or exchange not in (1, 2, 3):
            return "ineligible_security"
        stock = by_stock.get(permno)
        if stock is None or reference not in stock.index:
            return "missing_reference_price"
        prior = stock.loc[reference]
        price, basis = prior["prc"], prior["cfacpr"]
        if not np.isfinite(price):
            return "missing_reference_price"
        # On trading dates, the actual uses announcement-date share units even for
        # after-close news. On nontrading dates, require both adjacent bases to agree.
        announcement_session = calendar[first_session]
        actual_basis = stock["cfacpr"].get(announcement_session, np.nan)
        if not np.isfinite(actual_basis) or not np.isfinite(basis):
            return "missing_actual_split_basis"
        if not np.isclose(actual_basis, basis, rtol=1e-10, atol=0):
            return "actual_reference_split_change"

        counts = dict.fromkeys((
            "forecasts_missing_split_basis", "forecasts_other_split_basis",
            "forecasts_unlinked", "forecasts_missing_input",
        ), 0)
        selected, reason = consensus(
            by_forecast.get((base["ticker"], base["pends"])), when, permno,
            ticker_links, stock, calendar, basis, base["actual_eps_basis"], study, counts,
        )
        base.update(counts)
        if reason:
            return reason
        avg = selected["value"].mean()
        std = selected["value"].std(ddof=1)
        sue = (base["actual_eps"] - avg) / price
        dispersion = std / abs(avg) if abs(avg) >= study.consensus_floor else np.nan
        cap = price * prior["shrout"] / 1000
        trailing_momentum = returns_window(stock, market, ref - 251, ref - 21)
        trailing_volatility = returns_window(stock, market, ref - 59, ref)
        base.update(
            ibes_link_score=score, consensus_eps=avg, forecast_std_eps=std,
            forecast_eps_basis=selected["pdf"].iloc[0],
            analyst_count=len(selected), last_forecast_date=selected["anndats"].max(),
            last_activation_date=selected["actdats"].max(), price=price,
            market_cap_millions=cap, log_market_cap=np.log(cap), sue=sue, abs_sue=abs(sue),
            dispersion=dispersion, dispersion_price=std / price, sue_x_dispersion=sue * dispersion,
            momentum=np.prod(1 + trailing_momentum) - 1 if trailing_momentum is not None else np.nan,
            volatility=np.std(trailing_volatility, ddof=1) if trailing_volatility is not None else np.nan,
            abret_0=abnormal(stock, market, pos, pos),
        )
        for name, (left, right) in WINDOWS.items():
            base[name] = abnormal(stock, market, pos + left, pos + right)
        attach_fundamentals(base, by_ccm.get(permno), by_fund, reference, study)
        return None

    for base, reason in prepare_actuals(actuals, study):
        reason = reason or evaluate(base)
        if reason:
            rejected.append({**base, "reason": reason})
        else:
            records.append(base)

    panel = pd.DataFrame(records).reindex(columns=PANEL_COLUMNS)
    duplicates = panel.duplicated(["permno", "pends"], keep=False)
    rejected.extend(
        {**record, "reason": "duplicate_security_quarter"}
        for record in panel[duplicates].to_dict("records")
    )
    panel = panel[~duplicates].sort_values(["event_date", "permno", "pends"])
    exclusions = pd.DataFrame(rejected).reindex(columns=[
        *KEY, "announcement_date", "permno", "event_date", "reason",
        "forecasts_missing_input", "forecasts_unlinked", "forecasts_missing_split_basis",
        "forecasts_other_split_basis",
    ])
    return panel, exclusions


def run(input_dir, config, output_dir, clean_dir=None):
    if output_dir.exists():
        raise FileExistsError(f"Output directory already exists: {output_dir}")
    study = Study.load(config)
    sources = {
        "ibes": clean_ibes.load, "crsp": clean_crsp.load, "compustat": clean_compustat.load,
    }
    directories = {
        name: input_dir if clean_dir is None else clean_dir / name for name in sources
    }
    used = {
        "ibes_forecasts": directories["ibes"], "ibes_actuals": directories["ibes"],
        "crsp_daily": directories["crsp"], "crsp_market": directories["crsp"],
        "crsp_names": directories["crsp"], "compustat_quarterly": directories["compustat"],
        "ibes_crsp_link": input_dir, "ccm_link": input_dir,
    }

    def fingerprints():
        result = {}
        for name, directory in used.items():
            path = directory / f"{name}.csv"
            if not path.is_file():
                path = directory / f"{name}.csv.gz"
            with path.open("rb") as stream:
                result[path.name] = hashlib.file_digest(stream, "sha256").hexdigest()
        return result

    before = fingerprints()
    tables = {name: load(directories[name], study) for name, load in sources.items()}
    link_tables = links.load(input_dir, study)
    panel, excluded = build(study, **tables, link_tables=link_tables)
    if fingerprints() != before:
        raise DataError("An input changed during this run. Freeze the exports and retry.")
    audit = {
        "study": asdict(study),
        "runtime": {"python": platform.python_version(), "pandas": pd.__version__, "numpy": np.__version__},
        "input_sha256": before,
        "validated_rows": dict(zip(used, map(len, (*tables["ibes"], *tables["crsp"],
                                                   tables["compustat"], *link_tables)))),
        "panel_rows": len(panel),
        "excluded_rows": len(excluded),
        "exclusion_reasons": dict(Counter(excluded["reason"])),
        "missing_panel_values": panel.isna().sum().to_dict(),
        "event_timing": panel["timing"].value_counts().to_dict(),
        "fundamentals_status": panel["fundamentals_status"].value_counts().to_dict(),
    }
    publish(output_dir, {"event_panel": panel, "excluded_events": excluded}, audit)
    print(f"Wrote {len(panel)} events and {len(excluded)} exclusions to {output_dir}")
    if panel.empty:
        print("Event panel is empty. Review excluded_events.csv, audit.json and the sample dates.")


def main():
    cli = parser(__doc__, cleaned=True)
    # The all-in-one entry point accepts raw exports without staged cleaning.
    args = cli.parse_args()
    try:
        run(args.input_dir, args.config, args.output_dir, args.clean_dir)
    except (OSError, ValueError) as exc:
        cli.exit(2, f"error: {exc}\n")


if __name__ == "__main__":
    main()
