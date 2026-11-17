import csv
import gzip
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np
import pandas as pd

from examples.make_demo import write_demo
from src.data import clean_compustat, clean_crsp, clean_ibes, links
from src.data.common import DataError, Study
from src.data.merge_data import build, event_position

ROOT = Path(__file__).resolve().parents[1]


class PipelineTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.raw = self.root / "raw"
        write_demo(self.raw)
        self.config = ROOT / "config.toml"

    def mutate(self, table, edit):
        path = self.raw / f"{table}.csv"
        with path.open(newline="") as stream:
            reader = csv.DictReader(stream)
            header = reader.fieldnames
            rows = list(reader)
        edit(rows)
        with path.open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=header)
            writer.writeheader()
            writer.writerows(rows)

    def settings(self, old, new):
        target = self.root / "config.toml"
        target.write_text(self.config.read_text().replace(old, new))
        self.config = target

    def build(self):
        study = Study.load(self.config)
        return build(
            study, clean_ibes.load(self.raw, study), clean_crsp.load(self.raw, study),
            clean_compustat.load(self.raw, study), links.load(self.raw, study),
        )

    def test_consensus_controls_and_all_windows(self):
        panel, exclusions = self.build()
        row = panel.iloc[0]
        self.assertTrue(exclusions.empty)
        self.assertEqual(row.event_date, pd.Timestamp("2023-02-13"))
        self.assertEqual(row.reference_date, pd.Timestamp("2023-02-09"))
        self.assertEqual(row.last_activation_date, pd.Timestamp("2023-02-03"))
        self.assertEqual(row.analyst_count, 2)
        self.assertAlmostEqual(row.consensus_eps, 1.1)
        self.assertAlmostEqual(row.sue, 0.015)
        self.assertAlmostEqual(row.dispersion, np.sqrt(0.02) / 1.1)
        self.assertAlmostEqual(row.market_cap_millions, 100)
        self.assertAlmostEqual(row.book_to_market, 0.5)
        self.assertEqual(row.fundamentals_known_date, pd.Timestamp("2022-08-11"))
        self.assertAlmostEqual(row.abret_0, 0.019)
        self.assertAlmostEqual(row.car_m1_p1, 0.023)
        self.assertAlmostEqual(row.car_p2_p20, 0.038)
        self.assertAlmostEqual(row.car_p2_p60, 0.118)
        self.assertAlmostEqual(row.momentum, 1.003**231 - 1)
        self.assertAlmostEqual(row.volatility, 0)

    def test_actual_revision_does_not_replace_original(self):
        self.mutate("ibes_actuals", lambda rows: rows.append(
            dict(rows[0], anndats="2023-02-14", value="4.0")
        ))
        panel, _ = self.build()
        self.assertEqual(panel.iloc[0].actual_eps, 1.4)

    def test_conflicting_actuals_excluded(self):
        self.mutate("ibes_actuals", lambda rows: rows.append(dict(rows[0], value="3.0")))
        panel, exclusions = self.build()
        self.assertTrue(panel.empty)
        self.assertEqual(exclusions.iloc[0].reason, "conflicting_actual")

    def test_early_close_weekend_and_unknown_timing(self):
        market = pd.DataFrame({"close_seconds": [46800, 57600]}, index=pd.to_datetime(
            ["2023-11-24", "2023-11-27"]
        ))
        friday, monday = market.index
        self.assertEqual(event_position(market, friday, 46800, "exclude"), (1, "at_or_after_close"))
        self.assertEqual(event_position(market, friday, 46799, "exclude"), (0, "before_close"))
        self.assertEqual(event_position(market, friday, np.nan, "exclude"), (
            None, "unknown_announcement_time",
        ))
        self.assertEqual(event_position(market, friday, np.nan, "next_session"), (1, "unknown_next_session"))
        self.assertEqual(event_position(market, monday - pd.Timedelta(days=1), np.nan, "exclude"),
                         (1, "nontrading_day"))

    def test_same_score_conflict_is_not_a_join_fanout(self):
        self.mutate("ibes_crsp_link", lambda rows: rows.append(dict(rows[0], permno="999992")))
        panel, exclusions = self.build()
        self.assertTrue(panel.empty)
        self.assertEqual(exclusions.iloc[0].reason, "ambiguous_ibes_link")

    def test_ccm_ambiguity_leaves_event_and_null_fundamentals(self):
        self.mutate("ccm_link", lambda rows: rows.append(dict(rows[0], gvkey="000002")))
        panel, _ = self.build()
        self.assertEqual(panel.iloc[0].ccm_status, "ambiguous_ccm_link")
        self.assertTrue(pd.isna(panel.iloc[0].book_to_market))

    def test_missing_daily_return_invalidates_only_overlapping_windows(self):
        self.mutate("crsp_daily", lambda rows: rows.remove(
            next(row for row in rows if row["date"] == "2023-02-17")
        ))
        panel, _ = self.build()
        row = panel.iloc[0]
        self.assertAlmostEqual(row.car_m1_p1, 0.023)
        self.assertTrue(pd.isna(row.car_p2_p20))
        self.assertTrue(pd.isna(row.car_p2_p60))

    def test_different_forecast_share_basis_cannot_enter_consensus(self):
        def split(rows):
            next(row for row in rows if row["date"] == "2023-02-03")["cfacpr"] = "2"

        self.mutate("crsp_daily", split)
        panel, excluded = self.build()
        self.assertTrue(panel.empty)
        self.assertEqual(excluded.iloc[0].reason, "too_few_analysts")
        self.assertEqual(excluded.iloc[0].forecasts_other_split_basis, 1)

    def test_rdq_proxy_keeps_missing_rdq_missing(self):
        self.settings('fundamentals = "vintage"', 'fundamentals = "rdq"')
        self.mutate("compustat_quarterly", lambda rows: rows[0].update(rdq=""))
        panel, _ = self.build()
        self.assertEqual(panel.iloc[0].fundamentals_status, "no_eligible_quarter")

    def test_vintage_after_reference_cannot_replace_available_version(self):
        self.mutate("compustat_quarterly", lambda rows: rows.extend([
            dict(rows[0], available_date="2023-01-06", ceqq="55"),
            dict(rows[0], available_date="2023-02-09", ceqq="100"),
            dict(rows[0], available_date="2023-03-01", ceqq="200"),
        ]))
        panel, _ = self.build()
        self.assertEqual(panel.iloc[0].book_equity_millions, 55)
        self.assertEqual(panel.iloc[0].fundamentals_known_date, pd.Timestamp("2023-01-06"))

    def test_mixed_primary_and_diluted_forecasts_are_excluded(self):
        path = self.raw / "ibes_forecasts.csv"
        lines = path.read_text().splitlines()
        rows = [lines[0] + ",pdf"]
        rows.extend(line + (",D" if ",0002," in line else ",P") for line in lines[1:])
        path.write_text("\n".join(rows) + "\n")
        panel, excluded = self.build()
        self.assertTrue(panel.empty)
        self.assertEqual(excluded.iloc[0].reason, "mixed_forecast_eps_basis")

    def test_gzip_exports_and_duplicate_column_validation(self):
        path = self.raw / "ccm_link.csv"
        compressed = path.with_suffix(".csv.gz")
        compressed.write_bytes(gzip.compress(path.read_bytes()))
        path.unlink()
        self.assertEqual(len(self.build()[0]), 1)
        path.write_text("gvkey,lpermno,linkdt,linkenddt,linktype,linkprim,GVKEY\n")
        with self.assertRaisesRegex(DataError, "duplicate column names"):
            self.build()

    def test_legacy_delisting_return_compounds_once(self):
        self.settings('crsp_format = "ciz"', 'crsp_format = "legacy"')
        path = self.raw / "crsp_daily.csv"
        lines = path.read_text().splitlines()
        out = [lines[0] + ",dlret"]
        out.extend(line + (",-0.5" if "2023-02-13" in line else ",") for line in lines[1:])
        path.write_text("\n".join(out) + "\n")
        panel, _ = self.build()
        self.assertAlmostEqual(panel.iloc[0].abret_0, 1.02 * 0.5 - 1 - 0.001)

    def test_invalid_return_and_conflicting_keys_are_rejected(self):
        self.mutate("crsp_daily", lambda rows: rows.append(dict(rows[0], ret="0.02")))
        with self.assertRaisesRegex(DataError, "conflicting rows"):
            self.build()
        self.mutate("crsp_daily", lambda rows: rows[0].update(ret="-44"))
        with self.assertRaisesRegex(DataError, "crsp_daily.ret"):
            self.build()

    def test_cli_and_staged_outputs_match(self):
        def cli(module, output, *extra):
            return subprocess.run([
                sys.executable, "-m", module, "--input-dir", str(self.raw),
                "--output-dir", str(output), "--config", str(self.config), *extra,
            ], cwd=ROOT, capture_output=True, text=True)

        full = self.root / "full"
        staged = self.root / "staged"
        clean = self.root / "clean"
        first = cli("src.data", full)
        self.assertEqual(first.returncode, 0, first.stderr)
        for source in ("ibes", "crsp", "compustat"):
            result = cli(f"src.data.clean_{source}", clean / source)
            self.assertEqual(result.returncode, 0, result.stderr)
        result = cli("src.data.merge_data", staged, "--clean-dir", str(clean))
        self.assertEqual(result.returncode, 0, result.stderr)
        for name in ("event_panel.csv", "excluded_events.csv"):
            self.assertEqual((full / name).read_bytes(), (staged / name).read_bytes())
        self.assertTrue((full / "audit.json").is_file())
        repeat = cli("src.data", full)
        self.assertEqual(repeat.returncode, 2)
        self.assertIn("already exists", repeat.stderr)


if __name__ == "__main__":
    unittest.main()
