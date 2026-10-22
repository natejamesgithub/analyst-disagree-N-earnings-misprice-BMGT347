# Analyst Disagreement and Earnings Mispricing

BMGT347 — Quantitative Financial Analysis Final Project

## Overview

This project investigates whether disagreement among financial analysts affects how efficiently financial markets respond to earnings announcements.

Using analyst forecasts from I/B/E/S, equity returns from CRSP, and firm characteristics from Compustat, we examine whether greater analyst forecast dispersion before an earnings announcement changes the immediate and subsequent stock-price response to an earnings surprise.

The central question is:

> **Does analyst disagreement predict stronger market underreaction or post-earnings-announcement drift following earnings surprises?**

---

## Research Motivation

Earnings announcements provide investors with new information about firm performance. However, not all earnings announcements occur under the same level of uncertainty.

When analysts strongly disagree about a company's expected earnings, investors may also face greater uncertainty about the firm's underlying value. This project tests whether that disagreement affects how quickly earnings information is incorporated into stock prices.

Understanding this relationship may be useful to:

- equity analysts
- portfolio managers
- quantitative investors
- risk managers
- researchers studying market efficiency

---

## Research Questions

### Primary Question

Does analyst forecast dispersion prior to an earnings announcement affect the relationship between the earnings surprise and subsequent abnormal stock returns?

### Secondary Questions

1. Do firms with greater analyst disagreement experience larger announcement-day price reactions?

2. Does high analyst disagreement predict greater post-earnings-announcement drift?

3. Is the relationship different for positive and negative earnings surprises?

4. Does the relationship vary with firm size, analyst coverage, volatility, or valuation characteristics?

5. Can analyst disagreement provide economically useful information beyond the earnings surprise itself?

---

## Hypotheses

### H1 — Earnings Surprise

Larger positive earnings surprises will be associated with higher abnormal stock returns, while larger negative surprises will be associated with lower abnormal returns.

### H2 — Analyst Disagreement

Greater analyst forecast dispersion will be associated with greater uncertainty surrounding the earnings announcement.

### H3 — Interaction Effect

Analyst disagreement will modify the relationship between earnings surprises and abnormal returns.

The primary regression will therefore focus on the interaction:

`Earnings Surprise × Analyst Disagreement`

### H4 — Post-Earnings Drift

Stocks with large earnings surprises and high pre-announcement analyst disagreement may exhibit greater post-announcement abnormal returns if information is incorporated into prices more slowly.

---

## Data Sources

Data will primarily be obtained through Wharton Research Data Services (WRDS).

### I/B/E/S

Used for:

- individual analyst EPS forecasts
- consensus EPS estimates
- forecast dispersion
- analyst coverage
- actual reported EPS
- earnings announcement information

### CRSP

Used for:

- daily stock returns
- stock prices
- market capitalization
- market returns
- security identifiers

### Compustat

Used for firm-level control variables such as:

- total assets
- book equity
- profitability
- leverage
- revenue
- earnings
- valuation measures

---

## Sample

Planned sample:

**U.S. publicly traded firms, approximately 2005–2025**

The final sample period may be adjusted depending on data availability and the quality of database matches.

Potential filters include:

- U.S. common stocks
- NYSE, AMEX, and NASDAQ securities
- sufficient analyst coverage
- valid earnings-announcement dates
- available CRSP return observations
- required Compustat control variables

Detailed inclusion and exclusion rules will be documented in the final report.

---

## Key Variables

### Standardized Earnings Surprise

A standardized earnings-surprise measure will be constructed using actual and expected earnings.

Example:

```text
SUE = (Actual EPS - Consensus EPS) / Stock Price
```

Alternative standardizations will be tested as robustness checks.

### Analyst Disagreement

Analyst disagreement will be measured using dispersion among analyst forecasts.

Example:

```text
Dispersion = Standard Deviation of Analyst Forecasts / |Consensus Forecast|
```

Alternative measures may include:

- raw forecast standard deviation
- interquartile forecast range
- dispersion scaled by stock price
- dispersion percentile

### Abnormal Returns

Stock returns surrounding each earnings announcement will be compared against an appropriate expected-return benchmark.

Potential event windows include:

```text
[-1, +1]      Immediate announcement response
[+2, +20]     Short-term post-announcement drift
[+2, +60]     Longer-term post-announcement drift
```

---

## Methodology

### 1. Data Collection

Download the required datasets from WRDS and retain only variables required for the analysis.

Raw WRDS datasets will not be modified directly.

---

### 2. Data Cleaning

Cleaning procedures will include:

- standardizing dates
- removing duplicate observations
- treating missing values
- identifying invalid observations
- matching company identifiers across databases
- adjusting variables where necessary
- checking earnings-announcement timing
- validating analyst forecasts as information available before the announcement

Special attention will be given to preventing look-ahead bias.

---

### 3. Descriptive Analysis

Initial analysis will include:

- summary statistics
- variable distributions
- correlation matrix
- observations by year
- analyst coverage over time
- earnings-surprise distribution
- forecast-dispersion distribution

---

### 4. Event Study

Abnormal returns will be calculated around each earnings announcement.

The analysis will compare returns across different levels of:

- earnings surprise
- analyst disagreement
- analyst coverage
- firm size

---

### 5. Portfolio Sorts

Observations will be grouped into portfolios based on earnings surprise and analyst disagreement.

One potential structure is a two-dimensional sort:

| Earnings Surprise | Low Disagreement | Medium Disagreement | High Disagreement |
|---|---|---|---|
| Negative | | | |
| Neutral | | | |
| Positive | | | |

Average abnormal returns will then be compared across groups.

---

### 6. Regression Analysis

The primary regression specification will take the form:

```text
CAR =
    α
    + β1(Earnings Surprise)
    + β2(Analyst Disagreement)
    + β3(Earnings Surprise × Analyst Disagreement)
    + γ(Controls)
    + ε
```

The main coefficient of interest is:

```text
β3
```

This coefficient tests whether analyst disagreement changes the relationship between earnings surprises and abnormal returns.

Potential controls include:

- firm size
- book-to-market ratio
- prior stock momentum
- volatility
- analyst coverage
- profitability
- earnings-surprise magnitude
- industry
- year

---

## Benchmark Models

Results will be compared against simpler specifications.

### Benchmark 1

```text
CAR ~ Earnings Surprise
```

### Benchmark 2

```text
CAR ~ Earnings Surprise + Analyst Disagreement
```

### Full Model

```text
CAR ~ Earnings Surprise
      + Analyst Disagreement
      + Earnings Surprise × Analyst Disagreement
      + Controls
```

Comparing these models will determine whether analyst disagreement provides incremental explanatory power.

---

## Robustness Checks

Potential robustness tests include:

- alternative event windows
- alternative definitions of earnings surprise
- alternative measures of analyst disagreement
- winsorization of extreme observations
- positive vs. negative earnings surprises
- large vs. small companies
- high vs. low analyst coverage
- different sample periods
- industry controls
- year controls
- alternative expected-return benchmarks

---

## Expected Outputs

The project is expected to produce:

### Tables

- descriptive statistics
- correlation matrix
- portfolio-sort results
- main regression results
- robustness regressions

### Figures

- earnings-surprise distribution
- analyst-disagreement distribution
- abnormal returns around earnings announcements
- post-earnings cumulative abnormal-return curves
- disagreement × earnings-surprise heatmap
- regression interaction-effect visualization

### Final Deliverables

- final research paper
- presentation
- reproducible Python analysis
- processed analytical dataset
- figures and tables
- AI Workflow Appendix

---

## Repository Structure

```text
bmgt347-final-project/
│
├── README.md
├── requirements.txt
│
├── data/
│   ├── raw/
│   │   ├── ibes/
│   │   ├── crsp/
│   │   └── compustat/
│   │
│   └── processed/
│
├── src/
│   ├── data/
│   │   ├── clean_ibes.py
│   │   ├── clean_crsp.py
│   │   ├── clean_compustat.py
│   │   └── merge_data.py
│   │
│   ├── features/
│   │   ├── earnings_surprise.py
│   │   ├── analyst_dispersion.py
│   │   └── abnormal_returns.py
│   │
│   ├── analysis/
│   │   ├── descriptive.py
│   │   ├── event_study.py
│   │   ├── portfolio_sorts.py
│   │   ├── regressions.py
│   │   └── robustness.py
│   │
│   └── visualization/
│       └── figures.py
│
├── tests/
│   ├── test_data_cleaning.py
│   ├── test_features.py
│   └── test_returns.py
│
├── outputs/
│   ├── figures/
│   └── tables/
│
├── report/
│   ├── final_report.pdf
│   └── ai_workflow_appendix.pdf
│
└── presentation/
    └── final_presentation.pdf
```

---

## Reproducing the Analysis

### 1. Clone the Repository

```bash
git clone <repository-url>
cd bmgt347-final-project
```

### 2. Create a Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Obtain WRDS Data

Required datasets must be downloaded through an authorized WRDS account.

Place the raw datasets in their corresponding directories:

```text
data/raw/ibes/
data/raw/crsp/
data/raw/compustat/
```

Raw licensed WRDS data should not be committed to the public GitHub repository.

### 5. Build the Analytical Dataset

```bash
python src/data/clean_ibes.py
python src/data/clean_crsp.py
python src/data/clean_compustat.py
python src/data/merge_data.py
```

### 6. Construct Variables

```bash
python src/features/earnings_surprise.py
python src/features/analyst_dispersion.py
python src/features/abnormal_returns.py
```

### 7. Run the Analysis

```bash
python src/analysis/descriptive.py
python src/analysis/event_study.py
python src/analysis/portfolio_sorts.py
python src/analysis/regressions.py
python src/analysis/robustness.py
```

### 8. Generate Figures

```bash
python src/visualization/figures.py
```

Outputs will be stored in:

```text
outputs/figures/
outputs/tables/
```

---

## Validation

The project will include validation procedures designed to verify both AI-generated and manually written analysis.

Examples include:

- checking database merges using randomly selected firms
- manually verifying selected earnings announcements
- independently calculating abnormal returns for sample observations
- checking that analyst forecasts precede earnings announcements
- unit testing major feature calculations
- comparing descriptive results with known financial relationships
- inspecting extreme observations
- verifying regression sample sizes
- testing for look-ahead bias
- reproducing selected calculations independently

---

## AI Workflow

AI tools may be used to assist with:

- research design
- WRDS query development
- Python code generation
- debugging
- data-pipeline design
- unit-test generation
- statistical validation
- visualization
- documentation
- interpretation checks

AI-generated output will not automatically be assumed to be correct.

Important code and calculations will be validated through tests, independent calculations, benchmark comparisons, and manual inspection.

---

## AI Workflow Appendix

The final project will document:

1. AI tools used
2. purpose of each tool
3. representative prompts
4. AI-generated code or analysis
5. modifications made after human review
6. validation procedures
7. at least one documented AI error or incomplete result
8. how the error was detected and corrected

---

## Team Responsibilities

Final assignments will be determined by the team.

Possible workstreams include:

### Team Lead
- project coordination
- repository integration
- methodology consistency
- final deliverable integration

### Data Lead
- WRDS extraction
- database linking
- data cleaning
- sample construction

### Methodology Lead
- event-study design
- regression specifications
- hypothesis testing

### Analysis Lead
- portfolio sorts
- robustness analysis
- economic interpretation

### Reporting / Visualization Lead
- figures
- tables
- written report
- presentation
- AI Workflow Appendix

All team members will understand the project's core data, methodology, and results.

---

## Project Milestones

### Proposal Stage
- finalize research question
- verify WRDS dataset access
- identify required variables
- create repository structure
- assign workstreams

### Data Stage
- download WRDS datasets
- clean individual datasets
- build identifier links
- construct merged sample

### Analysis Stage
- construct research variables
- produce descriptive statistics
- complete event study
- estimate primary regression models

### Robustness Stage
- run alternative specifications
- test subsamples
- validate calculations
- finalize economic interpretation

### Reporting Stage
- generate final figures and tables
- complete written report
- complete AI Workflow Appendix
- prepare final presentation

---

## Authors

BMGT347 Final Project Team

- **Team Lead:** TBD
- Team Member: TBD
- Team Member: TBD
- Team Member: TBD
- Team Member: TBD

University of Maryland  
Robert H. Smith School of Business  
Fall 2026