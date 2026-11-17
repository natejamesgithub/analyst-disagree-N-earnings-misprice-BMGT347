"""Generate invented inputs."""

import argparse
import csv
from datetime import date, timedelta
from pathlib import Path


def write_demo(root):
    root.mkdir(parents=True, exist_ok=True)
    days = [date(2022, 1, 3) + timedelta(days=i) for i in range(800)]
    sessions = [day for day in days if day.weekday() < 5]
    names = {
        "ibes_forecasts": [
            ("ZZTEST", "2022-12-31", "0001", "010", "2023-01-20", "2023-01-20", 1.1, "EPS", 6, "USD"),
            ("ZZTEST", "2022-12-31", "0001", "010", "2023-02-01", "2023-02-02", 1.2, "EPS", 6, "USD"),
            ("ZZTEST", "2022-12-31", "0002", "011", "2023-02-03", "2023-02-03", 1.0, "EPS", 6, "USD"),
            ("ZZTEST", "2022-12-31", "0003", "012", "2023-02-03", "2023-02-10", 9.9, "EPS", 6, "USD"),
            ("ZZTEST", "2022-12-31", "0002", "011", "2023-02-10", "2023-02-10", 7.0, "EPS", 6, "USD"),
        ],
        "ibes_actuals": [("ZZTEST", "2022-12-31", "2023-02-10", 1.4, "EPS", "QTR", "USD", "16:01")],
        "crsp_daily": [
            (999991, day, 0.02 if day.isoformat() == "2023-02-13" else 0.003, 20, 5000, 1)
            for day in sessions
        ],
        "crsp_market": [(day, 0.001, "16:00") for day in sessions],
        "crsp_names": [(999991, "2020-01-01", "", 11, 3)],
        "compustat_quarterly": [
            ("000001", "2022-06-30", 50, "USD", "INDL", "STD", "D", "C", "2022-08-10", "2022-08-11"),
            ("000001", "2022-12-31", 99, "USD", "INDL", "STD", "D", "C", "2023-02-10", "2023-02-13"),
        ],
        "ibes_crsp_link": [("ZZTEST", 999991, "2020-01-01", "", 0)],
        "ccm_link": [("000001", 999991, "2020-01-01", "", "LC", "P")],
    }
    schemas = Path(__file__).parent / "schemas"
    for name, rows in names.items():
        header = (schemas / f"{name}.csv").read_text().strip().split(",")
        with (root / f"{name}.csv").open("x", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(header)
            writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    write_demo(parser.parse_args().directory)


if __name__ == "__main__":
    main()
