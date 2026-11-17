# BMGT347 | Analyst Disagreement and Earnings Mispricing

Does pre-announcement analyst disagreement change how quarterly earnings surprises relate to the immediate stock-price response and subsequent drift? The data pipeline links U.S. I/B/E/S forecasts and actuals to CRSP and Compustat. It produces an earnings-event panel for the proposed surprise × disagreement regression and two-way portfolio sorts. The default announcement sample spans 2005–2025.

## Run the synthetic example

From the repository root, use Python 3.11 or newer.

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m examples.make_demo data/demo_raw
python -m src.data --input-dir data/demo_raw --output-dir runs/demo
python -m unittest discover -s tests -v
```

The invented example produces one event dated February 13, 2023, with two analysts, consensus EPS of 1.10, SUE of 0.015, and CARs of 0.023, 0.038, and 0.118. Its calendar is synthetic. Use a new output directory for every invocation. Input schema headers are under [examples/schemas](examples/schemas/).

## Export private WRDS inputs

Use your institution's WRDS web queries or authorized WRDS SQL session. The pipeline takes locally exported files and runs offline. Download each table as CSV, then select or alias the columns below. CSVs compressed with gzip also work. Use UTF-8, ISO dates (`YYYY-MM-DD`), decimal returns (0.01 means 1%), and blank fields for missing values. Convert vendor-specific missing sentinels and open-date placeholders to blanks before running. Preserve leading zeros in string IDs. Column names are case-insensitive and extra columns are ignored.

| File stem | WRDS source and canonical fields |
| --- | --- |
| `ibes_forecasts` | U.S. **unadjusted** Detail EPS History, commonly `ibes.detu_epsus`. Export `ticker, fpedats, estimator, analys, anndats, actdats, value, measure, fpi, curr` and `pdf` if available. Filter to USD, EPS, and quarterly FPI codes `6,7,8,9,N,O,P,Q,Y`. `anndats` is the estimate issue date and `actdats` is its vendor activation date. |
| `ibes_actuals` | U.S. **unadjusted** Actual EPS History, commonly `ibes.actu_epsus`. Export `ticker, pends, anndats, value, measure, pdicity, curr_act AS curr`, and `anntims` if available. Filter to USD, EPS, and `QTR`. Use the first-release series and keep original observations if the export contains revisions. Supply optional `eps_basis` when the actual's primary/diluted basis is independently available. |
| `ibes_crsp_link` | [WRDS I/B/E/S–CRSP Link](https://wrds-www.wharton.upenn.edu/pages/wrds-research/database-linking-matrix/linking-ibes-with-crsp/). Export historical `ticker, permno, sdate, edate, score`. Include all candidate links and their effective dates. |
| `crsp_daily` | CRSP daily stock data. For CIZ, alias `dlycaldt AS date, dlyret AS ret, dlyprc AS prc, dlyshrout AS shrout` and the daily cumulative price factor `dlycumfacpr AS cfacpr`, include `permno`. Join the daily cumulative factor file on `permno, dlycaldt` if the factor is supplied separately. Use one row per security/session and raw prices with shares outstanding in thousands. [CRSP CIZ data guide](https://www.crsp.org/crsp_pdf/crsp-us-stock-indexes-databases-guide-flat-file-format-2-0/) |
| `crsp_market` | CRSP daily broad-market value-weighted total return series. Use `date, vwretd` and add actual scheduled session close `close_time` in New York local time. Keep one row for every exchange session, including early-close sessions. The official market dates, combined with historical exchange hours, determine the event clock. [CRSP historical indexes](https://www.crsp.org/research__trashed/crsp-historical-indexes/), [NYSE hours and calendars](https://www.nyse.com/trade/hours-calendars) |
| `crsp_names` | Historical security metadata with `permno, namedt, nameendt, shrcd, exchcd` in the canonical format below. Use intervals covering the entire requested sample. |
| `ccm_link` | CRSP/Compustat Merged Link History, commonly `crsp.ccmxpf_lnkhist`. Export `gvkey, lpermno, linkdt, linkenddt, linktype, linkprim`. [WRDS CCM linking guide](https://wrds-www.wharton.upenn.edu/pages/wrds-research/database-linking-matrix/linking-compustat-with-crsp/) |
| `compustat_quarterly` | Compustat North America quarterly fundamentals. Export `gvkey, datadate, ceqq, curcdq, indfmt, datafmt, popsrc, consol` with `USD, INDL, STD, D, C`. CEQQ is common equity in USD millions. Also supply `available_date` for vintage mode or `rdq` for the standard quarterly export in proxy mode. |

**CIZ security metadata.** Use historical security information rather than the current header. Alias `secinfostartdt` and `secinfoenddt` to `namedt` and `nameendt`. A canonical recode for this study sets `shrcd=11` for `securitytype='EQUTY'`, `securitysubtype='COM'`, `sharetype='COM'`, `usincflg='Y'`, and `issuertype IN ('CORP','ACOR')`, and `0` otherwise. Map `primaryexch` N/A/Q to `exchcd` 1/2/3 respectively, and other values to 0. The CIZ rule approximates the historical common-share screen. For legacy names data, export the native share and exchange codes. Keep the dated history for ineligible rows as well so the audit can distinguish missing metadata from ineligibility.

**Legacy CRSP.** Set `crsp_format = "legacy"`. Export DSF returns and add `dlret` from the daily delisting file, aligned to the applicable CRSP market session using the vendor's date convention. Include a row for a delisting-only return if present. The cleaner compounds the stock and delisting legs when both exist and uses the observed leg when only one exists. CIZ uses `dlyret` as supplied.

**Announcement times.** Convert genuine timestamps to New York wall time, including daylight saving, before exporting as `HH:MM[:SS]`. For a WRDS time stored as seconds since midnight, apply the correct source timezone and format it as clock time. Blank out any placeholder times per the source dictionary. Dates and times must describe the same local announcement. Keep all original actual dates for each included ticker/quarter, including any first release outside the sample.

**Fundamentals availability.** The default `vintage` mode requires dated as-reported CEQQ values. Use a point-in-time history with the actual availability date of each version, or pair Compustat with a verified original filing value and its public filing date. Blank availability leaves the quarter ineligible. If your WRDS access provides only standard Compustat `fundq`, set `fundamentals = "rdq"` and export `rdq`. This proxy waits until the later of RDQ and fiscal period end plus 90 calendar days. It can still expose revised values from a later data vintage. Report proxy-based results separately from any point-in-time specification.

**Coverage.** Include at least 252 market sessions before the first announcement and 61 after the last, plus sufficient calendar padding for holidays. Include forecast history back through the configured forecast lookback and fundamentals through the maximum age. Keep delisted securities. To manage memory, export CRSP daily data only for candidate PERMNOs from the historical I/B/E/S link table and use a small sample first. For larger pulls, run disjoint announcement-year configurations with padded inputs and retain their separate audits. The market calendar must cover every exported daily return date. Missing observations in the return windows remain visible as missing outcomes.

## Run the study

Set `start` and `end` in a copy of [config.toml](config.toml) for your extraction. Place the eight private inputs under `data/raw`.

```sh
python -m src.data --config config.toml --input-dir data/raw --output-dir runs/study
```

For separate cleaning and handoff steps, run:

```sh
python -m src.data.clean_ibes --input-dir data/raw --output-dir data/clean/ibes
python -m src.data.clean_crsp --input-dir data/raw --output-dir data/clean/crsp
python -m src.data.clean_compustat --input-dir data/raw --output-dir data/clean/compustat
python -m src.data.merge_data --input-dir data/raw --clean-dir data/clean --output-dir runs/staged
```

Pass the same `--config` to every stage when using a custom file. The staged merge revalidates cleaned exports and reads the two link tables from the raw directory. Invalid schemas and conflicting daily or accounting keys produce errors. The run writes all deliverables together into a new directory.

## Event construction and output

- **Signal cutoff.** A forecast must have been issued within the prior 90 calendar days and activated strictly before the announcement date. The pipeline takes the latest eligible issue per broker–analyst pair. Unresolved conflicting issues or original actuals exclude the event. When the actual's EPS basis is known, selected forecasts must match it. Otherwise the retained forecast flags must agree, or all be absent. The optional basis fields in the panel show what the source supports.
- **Historical identity.** Match the I/B/E/S ticker to the lowest eligible WRDS link score, using scores 0–1 by default. Require a unique PERMNO on the announcement and the same PERMNO on the reference and retained forecast issue dates. Apply historical CRSP metadata at the reference date. Attach Compustat with active CCM LC/LU and P/C links on that date. Ambiguous CCM matches leave accounting controls missing.
- **Price and EPS units.** The reference is the final exchange session strictly before the announcement calendar date, including for after-close reports. The pipeline uses absolute raw CRSP price. It requires matching CRSP cumulative price factors for forecast issue, reference, and announcement share bases. Forecasts across factor changes are removed, and an actual/reference factor change excludes the event. On a nontrading announcement date, the adjacent session factors must agree. This conservative screen can also remove other price-adjusting distributions and cannot resolve every vendor EPS-basis discrepancy. [WRDS note on unadjusted I/B/E/S data](https://wrds-www.wharton.upenn.edu/documents/5/A_Note_on_IBES_Unadjusted_Data_pdf.pdf)
- **Timing and returns.** Announcements before the close map to that session. Reports at or after the close or on nontrading dates map to the next session. Missing times on trading days are excluded by default. The `next_session` option assigns and labels them explicitly. Abnormal return equals stock total return minus CRSP's market return. The CARs sum abnormal returns over `[-1,+1]`, `[+2,+20]`, and `[+2,+60]` on the market calendar. A missing stock return or calendar boundary leaves the affected window blank.
- **Signals.** `sue` is actual EPS minus mean forecast EPS, divided by reference price. `dispersion` is the sample standard deviation of forecast EPS divided by the absolute consensus, blank when the consensus magnitude is below one cent by default. `dispersion_price` uses reference price as the denominator. `abs_sue`, `analyst_count`, and `sue_x_dispersion` support the proposed specifications.
- **Controls.** Security market capitalization is raw price × shares outstanding in millions, with a natural-log counterpart. Momentum compounds the 231 daily stock returns ending 21 sessions before the reference session. Volatility is the daily sample standard deviation over 60 sessions ending on the reference session. Book-to-market divides positive common equity by security market capitalization, so multi-class capital structures can affect this ratio. Accounting selection takes the latest fiscal period known strictly before the reference date and then its latest available vintage.

| Output | Contents |
| --- | --- |
| `event_panel.csv` | One row per matched PERMNO and fiscal quarter with timing, input dates, identifiers, controls, and outcomes. Read GVKEY and I/B/E/S ticker as strings. Retain blank values and select complete cases per specification. |
| `excluded_events.csv` | Excluded ticker-quarter observations with reason codes and forecast-screening counts where evaluated. Duplicate ticker histories mapping to the same security-quarter are excluded when multiple candidate rows survive. |
| `audit.json` | Input SHA-256 hashes, effective configuration, runtime versions, validated row counts, exclusion counts, timing counts, and per-column missing counts. A staged run hashes the staged inputs it reads. |

The event panel supports an observational analysis. Daily returns for an intraday announcement include the pre-release part of that session. The event windows can overlap across quarters or firms, and complete long-horizon windows can favor securities with continuous trading. I/B/E/S revisions and contributor coverage can vary by vendor snapshot. Use independently verified initial actuals for the surprise measure and record the extraction date.

## Course reproducibility and handoff

Keep WRDS inputs, cleaned files, event-level outputs, and credentials local. The ignored directories are `data/` and `runs/`. The example generator and schema headers contain only invented or structural information. Commit the pipeline, configuration, and tests, and record the export queries, vendor snapshot dates, sample attrition, and exact run command in the team's research record. Add the team roster, lead, and links to the report, presentation, and analysis outputs when those are integrated into the group repository.

For the required AI Workflow Appendix, record the prompt that requested this pipeline, the code and tests Codex generated, and the checks the team performs on authorized exports. Reconcile several events by hand against the original timestamps, historical links, forecasts, and CAR windows. Preserve an example of a correction your team actually verified, including the evidence and fix.
