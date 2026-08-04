"""End-to-end guarantees for the recursive learning stack."""

from __future__ import annotations

import datetime as dt
import math
import random
import tempfile
import unittest
from pathlib import Path
from typing import Tuple

import learning
import model_registry
import shadow_journal
from challenger import BaseRateChampion, LogisticChallenger
from feature_store import FEATURE_NAMES, FeatureStore, build_features, research_eligible
from learning_dataset import build_dataset, build_rows, dataset_summary
from outcome_source import OutcomeSource
from test_outcome_source import _write
from validation import (
    apply_split,
    brier_score,
    brier_skill,
    calibration_slope_intercept,
    expected_calibration_error,
    leakage_violations,
    log_loss,
    score_predictions,
    walk_forward_splits,
)


def _synthetic_archive(database: Path, securities: int = 6, sessions: int = 420,
                       seed: int = 7, learnable: bool = True,
                       jump_probability: float = 0.06,
                       jump_size: Tuple[float, float] = (0.05, 0.12)) -> None:
    """Build an archive where volatility genuinely predicts big moves.

    A model that cannot find this signal is broken; a model that finds signal in
    the ``learnable=False`` version is overfitting.
    """
    generator = random.Random(seed)
    rows = []
    session = dt.date(2024, 1, 1)
    dates = []
    while len(dates) < sessions:
        if session.weekday() < 5:
            dates.append(session.isoformat())
        session += dt.timedelta(days=1)

    spy = 100.0
    spy_series = []
    for _ in dates:
        spy *= 1 + generator.gauss(0.0003, 0.008)
        spy_series.append(spy)
    for date, close in zip(dates, spy_series):
        rows.append((date, "SPY", close, close, True))

    for index in range(securities):
        ticker = f"AA{index:02d}"
        price = 50.0 + index
        # Half the securities are structurally jumpy, half are calm.
        jumpy = index % 2 == 0
        for position, date in enumerate(dates):
            noise = generator.gauss(0.0, 0.02 if (jumpy and learnable) else 0.006)
            if learnable and jumpy and generator.random() < jump_probability:
                noise += generator.choice([-1, 1]) * generator.uniform(*jump_size)
            price = max(2.5, price * (1 + noise))
            rows.append((date, ticker, price, spy_series[position], True))
    _write(database, rows)

    # Dollar volume is stored separately by the pipeline; fill it so the
    # liquidity screen can pass.
    import sqlite3
    connection = sqlite3.connect(str(database))
    connection.execute(
        "UPDATE swing_observations SET median_dollar_volume_20d = 25000000 WHERE ticker != 'SPY'"
    )
    connection.execute("UPDATE swing_observations SET median_dollar_volume_20d = 900000000 WHERE ticker = 'SPY'")
    connection.commit()
    connection.close()


class FeatureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.database = Path(self.directory.name) / "market-history.sqlite3"
        _synthetic_archive(self.database)

    def test_features_never_read_a_later_session(self) -> None:
        history = next(FeatureStore(self.database).iter_histories(tickers=["AA00"]))
        index = 200
        full = build_features(history, index)

        truncated = type(history)(history.ticker, history.security_id)
        for position in range(index + 1):
            truncated.append(history.dates[position], history.closes[position],
                             history.benchmarks[position], history.volumes[position],
                             history.clean[position])
        limited = build_features(truncated, index)
        self.assertEqual(full["values"], limited["values"])

    def test_early_sessions_report_missing_features_rather_than_guessing(self) -> None:
        history = next(FeatureStore(self.database).iter_histories(tickers=["AA00"]))
        early = build_features(history, 3)
        self.assertFalse(early["complete"])
        self.assertIn("excess_return_126d", early["missing"])
        self.assertIsNone(early["values"]["excess_return_126d"])

    def test_liquidity_screen_reports_market_value_as_unavailable(self) -> None:
        history = next(FeatureStore(self.database).iter_histories(tickers=["AA00"]))
        screen = research_eligible(history, 200)
        self.assertEqual(screen["marketValueScreen"], "unavailable")
        self.assertTrue(screen["eligible"])


class DatasetTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.database = Path(self.directory.name) / "market-history.sqlite3"
        _synthetic_archive(self.database)

    def test_labels_are_measured_after_a_delayed_entry(self) -> None:
        history = next(FeatureStore(self.database).iter_histories(tickers=["AA00"]))
        rows = build_rows(history, horizon=5)
        self.assertTrue(rows)
        for row in rows[:20]:
            self.assertGreater(row["entryDate"], row["sessionDate"])
            self.assertGreater(row["exitDate"], row["entryDate"])

    def test_benchmark_is_excluded_from_the_research_set(self) -> None:
        rows = build_dataset(5, database=self.database)
        self.assertNotIn("SPY", {row["ticker"] for row in rows})

    def test_summary_states_what_the_data_contains(self) -> None:
        rows = build_dataset(5, database=self.database)
        summary = dataset_summary(rows, 5)
        self.assertGreater(summary["rows"], 100)
        self.assertEqual(summary["securities"], 6)
        self.assertIsNotNone(summary["bigMoveRate"])
        self.assertIn("close one session after", summary["entryConvention"])


class ValidationTests(unittest.TestCase):
    def test_scores_reward_the_better_forecast(self) -> None:
        outcomes = [1, 0, 1, 0] * 25
        confident = [0.9 if outcome else 0.1 for outcome in outcomes]
        vague = [0.5] * len(outcomes)
        self.assertLess(brier_score(confident, outcomes), brier_score(vague, outcomes))
        self.assertLess(log_loss(confident, outcomes), log_loss(vague, outcomes))
        self.assertGreater(brier_skill(confident, outcomes), 0)
        self.assertAlmostEqual(brier_skill(vague, outcomes), 0.0, places=6)

    def test_overconfidence_shows_as_a_calibration_slope_below_one(self) -> None:
        generator = random.Random(3)
        rows = []
        for _ in range(4000):
            true_probability = generator.uniform(0.05, 0.95)
            outcome = 1 if generator.random() < true_probability else 0
            logit = math.log(true_probability / (1 - true_probability))
            stated = 1 / (1 + math.exp(-logit * 2.0))  # exaggerated confidence
            rows.append((stated, outcome))
        fit = calibration_slope_intercept([row[0] for row in rows], [row[1] for row in rows])
        self.assertLess(fit["slope"], 0.8)

    def test_a_perfectly_calibrated_forecast_has_near_zero_error(self) -> None:
        generator = random.Random(5)
        probabilities, outcomes = [], []
        for _ in range(6000):
            probability = generator.uniform(0.05, 0.95)
            probabilities.append(probability)
            outcomes.append(1 if generator.random() < probability else 0)
        self.assertLess(expected_calibration_error(probabilities, outcomes), 0.03)
        fit = calibration_slope_intercept(probabilities, outcomes)
        self.assertGreater(fit["slope"], 0.85)
        self.assertLess(fit["slope"], 1.15)

    def test_folds_are_chronological_and_never_overlap(self) -> None:
        dates = [f"2025-{month:02d}-{day:02d}" for month in range(1, 13) for day in range(1, 21)]
        folds = walk_forward_splits(dates, horizon_sessions=5, outer_periods=5)
        self.assertEqual(len(folds), 5)
        for fold in folds:
            self.assertLess(fold["trainEnd"], fold["testStart"])
        for earlier, later in zip(folds, folds[1:]):
            self.assertLess(earlier["testEnd"], later["testStart"])

    def test_training_rows_resolving_inside_the_test_period_are_purged(self) -> None:
        rows = [
            {"sessionDate": "2025-01-01", "exitDate": "2025-01-08", "ticker": "A"},
            {"sessionDate": "2025-01-05", "exitDate": "2025-01-12", "ticker": "B"},
            {"sessionDate": "2025-01-20", "exitDate": "2025-01-27", "ticker": "C"},
        ]
        fold = {"fold": 1, "trainStart": "2025-01-01", "trainEnd": "2025-01-09",
                "testStart": "2025-01-10", "testEnd": "2025-01-31"}
        train, test = apply_split(rows, fold)
        self.assertEqual([row["ticker"] for row in train], ["A"])
        self.assertEqual(fold["purgedRows"], 1)
        self.assertEqual([row["ticker"] for row in test], ["C"])
        self.assertEqual(leakage_violations(train, test), [])

    def test_leakage_check_catches_a_bad_split(self) -> None:
        train = [{"sessionDate": "2025-02-01", "exitDate": "2025-02-08", "ticker": "A"}]
        test = [{"sessionDate": "2025-01-20", "exitDate": "2025-01-27", "ticker": "C"}]
        self.assertTrue(leakage_violations(train, test))

    def test_confidence_interval_clusters_by_date(self) -> None:
        rows = [{"sessionDate": f"2025-01-{day:02d}", "probability": 0.5, "label": day % 2}
                for day in range(1, 29)]
        result = score_predictions(rows)
        self.assertEqual(result["brierSkillInterval"]["clusters"], 28)


class ChallengerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.database = Path(self.directory.name) / "market-history.sqlite3"

    def test_champion_predicts_the_training_base_rate(self) -> None:
        rows = [{"bigMove": 1}] * 30 + [{"bigMove": 0}] * 70
        champion = BaseRateChampion().fit(rows, "bigMove")
        self.assertAlmostEqual(champion.rate, 0.3, places=6)
        self.assertAlmostEqual(champion.predict({}), 0.3, places=6)

    def test_challenger_learns_a_real_signal(self) -> None:
        _synthetic_archive(self.database, securities=10, sessions=600, learnable=True,
                           jump_probability=0.14, jump_size=(0.10, 0.22))
        rows = build_dataset(5, database=self.database)
        self.assertGreater(len(rows), 200)
        # The signal must actually be present, or the test proves nothing.
        self.assertGreater(sum(row["bigMove"] for row in rows), 100)
        split = int(len(rows) * 0.7)
        train, test = rows[:split], rows[split:]
        challenger = LogisticChallenger().fit(train, "bigMove")
        champion = BaseRateChampion().fit(train, "bigMove")

        predictions = [{"probability": challenger.predict(row), "label": row["bigMove"],
                        "sessionDate": row["sessionDate"]} for row in test]
        baseline = [{"probability": champion.predict(row), "label": row["bigMove"],
                     "sessionDate": row["sessionDate"]} for row in test]
        self.assertLess(score_predictions(predictions)["brier"], score_predictions(baseline)["brier"])

    def test_challenger_reports_readable_coefficients(self) -> None:
        _synthetic_archive(self.database)
        rows = build_dataset(5, database=self.database)
        description = LogisticChallenger().fit(rows, "bigMove").describe()
        self.assertEqual(set(description["coefficients"]), set(FEATURE_NAMES))
        self.assertEqual(len(description["strongestFeatures"]), 3)


class ExperimentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        root = Path(self.directory.name)
        self.database = root / "market-history.sqlite3"
        for module, attribute, path in (
            (model_registry, "INVENTORY_PATH", root / "inventory.json"),
            (model_registry, "EXPERIMENTS_PATH", root / "experiments.json"),
            (shadow_journal, "SHADOW_PATH", root / "shadow.json"),
        ):
            original = getattr(module, attribute)
            setattr(module, attribute, path)
            self.addCleanup(setattr, module, attribute, original)

    def test_an_empty_archive_produces_a_failed_verdict_not_a_crash(self) -> None:
        result = learning.run_experiment("bigMove", 5, database=self.database, register=False)
        self.assertEqual(result["verdict"], "failed")
        self.assertTrue(result["gateFailures"])
        self.assertIn("No live recommendation changes", result["outcome"])

    def test_experiment_runs_walk_forward_and_records_the_result(self) -> None:
        _synthetic_archive(self.database, sessions=500)
        result = learning.run_experiment("bigMove", 5, database=self.database,
                                         register=True, notes="unit test")
        self.assertGreaterEqual(result["scoredFolds"], 3)
        for fold in result["folds"]:
            if fold["status"] == "scored":
                self.assertLess(fold["trainEnd"], fold["testStart"])
        registered = model_registry.experiments()
        self.assertEqual(len(registered), 1)
        self.assertEqual(registered[0]["verdict"], result["verdict"])

    def test_a_failed_experiment_is_still_registered(self) -> None:
        learning.run_experiment("bigMove", 5, database=self.database, register=True)
        entries = model_registry.experiments()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["verdict"], "failed")
        self.assertTrue(entries[0]["gateFailures"])

    def test_noise_alone_does_not_pass_the_gates(self) -> None:
        _synthetic_archive(self.database, sessions=500, learnable=False, seed=99)
        result = learning.run_experiment("bigMove", 5, database=self.database, register=False)
        self.assertEqual(result["verdict"], "failed")

    def test_status_is_honest_when_no_archive_exists(self) -> None:
        status = learning.learning_status(Path(self.directory.name) / "absent.sqlite3")
        self.assertEqual(status["status"], "waiting-for-archive")
        self.assertIn("No model influences a live recommendation", status["liveInfluence"])


class ShadowRunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        root = Path(self.directory.name)
        self.database = root / "market-history.sqlite3"
        self.shadow = root / "shadow.json"
        original = shadow_journal.SHADOW_PATH
        shadow_journal.SHADOW_PATH = self.shadow
        self.addCleanup(setattr, shadow_journal, "SHADOW_PATH", original)
        source_original = shadow_journal.shared_source
        shadow_journal.shared_source = lambda: OutcomeSource(self.database)
        self.addCleanup(setattr, shadow_journal, "shared_source", source_original)

    def test_shadow_run_predicts_forward_and_freezes_the_result(self) -> None:
        _synthetic_archive(self.database, securities=8, sessions=500,
                           jump_probability=0.14, jump_size=(0.10, 0.22))
        result = learning.run_shadow_session(database=self.database)
        self.assertEqual(result["status"], "recorded")
        self.assertGreater(result["predictionsAppended"], 0)
        self.assertIn("Shadow only", result["visibility"])

        stored = shadow_journal._load(self.shadow)
        # Every prediction is for the newest session, so none can be graded yet.
        self.assertEqual({row["sessionDate"] for row in stored}, {result["sessionDate"]})
        self.assertTrue(all(row["predictionHash"] for row in stored))

    def test_the_shadow_model_never_trains_on_the_session_it_predicts(self) -> None:
        _synthetic_archive(self.database, securities=8, sessions=500,
                           jump_probability=0.14, jump_size=(0.10, 0.22))
        result = learning.run_shadow_session(database=self.database)
        rows = build_dataset(5, database=self.database)
        training = [row for row in rows if row["exitDate"] < result["sessionDate"]]
        self.assertEqual(result["trainingRows"], len(training))
        self.assertTrue(all(row["exitDate"] < result["sessionDate"] for row in training))

    def test_an_empty_archive_records_nothing(self) -> None:
        result = learning.run_shadow_session(database=self.database)
        self.assertEqual(result["status"], "not-ready")
        self.assertEqual(shadow_journal._load(self.shadow), [])


class ModelRiskTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        root = Path(self.directory.name)
        self.database = root / "market-history.sqlite3"
        self.shadow = root / "shadow.json"

    def test_report_flags_a_missing_archive_as_a_risk_event(self) -> None:
        import model_risk
        report = model_risk.model_risk_report(database=self.database, shadow_path=self.shadow)
        self.assertEqual(report["status"], "attention")
        self.assertIn("The adjusted market-history archive is unavailable", report["modelRiskEvents"])

    def test_stable_data_produces_no_risk_event(self) -> None:
        import model_risk
        _synthetic_archive(self.database, securities=6, sessions=420)
        report = model_risk.model_risk_report(database=self.database, shadow_path=self.shadow)
        self.assertGreater(report["researchRows"], 100)
        self.assertTrue(report["featureDrift"])
        self.assertNotIn("The adjusted market-history archive is unavailable",
                         report["modelRiskEvents"])

    def test_a_constant_feature_is_never_reported_as_drifting(self) -> None:
        import model_risk
        rows = [
            {"sessionDate": f"2026-01-{day:02d}",
             "features": {name: 1.0 for name in FEATURE_NAMES}}
            for day in range(1, 29)
        ]
        drift = model_risk.feature_drift(rows, recent_sessions=5)
        self.assertTrue(drift)
        self.assertEqual({item["severity"] for item in drift}, {"constant"})
        self.assertTrue(all(item["shift"] is None for item in drift))

    def test_drift_is_detected_when_the_market_changes(self) -> None:
        import model_risk
        _synthetic_archive(self.database, securities=6, sessions=420)
        rows = build_dataset(5, database=self.database)
        dates = sorted({row["sessionDate"] for row in rows})
        boundary = dates[-21]
        shifted = [
            {**row, "features": {**row["features"], "volatility_21d": row["features"]["volatility_21d"] + 5}}
            if row["sessionDate"] >= boundary else row
            for row in rows
        ]
        drift = model_risk.feature_drift(shifted)
        worst = drift[0]
        self.assertEqual(worst["feature"], "volatility_21d")
        self.assertEqual(worst["severity"], "serious")


class RegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.inventory = Path(self.directory.name) / "inventory.json"

    def test_approval_changes_append_rather_than_overwrite(self) -> None:
        model_registry.register_model(
            "big-move", "Big-move probability", "logistic", "1", ["prices"],
            "Research only", "Uncalibrated", approval="research", path=self.inventory,
        )
        model_registry.register_model(
            "big-move", "Big-move probability", "logistic", "1", ["prices"],
            "Shadow run", "Uncalibrated", approval="shadow", path=self.inventory,
        )
        history = model_registry.model_history("big-move", self.inventory)
        self.assertEqual([entry["approval"] for entry in history], ["research", "shadow"])
        current = model_registry.current_models(self.inventory)
        self.assertEqual(len(current), 1)
        self.assertEqual(current[0]["approval"], "shadow")

    def test_unknown_approval_state_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            model_registry.register_model(
                "x", "y", "z", "1", [], "", "", approval="live-now", path=self.inventory,
            )


class ShadowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        root = Path(self.directory.name)
        self.path = root / "shadow.json"
        self.database = root / "market-history.sqlite3"
        original = shadow_journal.shared_source
        shadow_journal.shared_source = lambda: OutcomeSource(self.database)
        self.addCleanup(setattr, shadow_journal, "shared_source", original)

    def test_shadow_predictions_are_frozen_and_hashed(self) -> None:
        first = shadow_journal.record_shadow_predictions(
            "big-move", "1", "2026-01-05",
            [{"symbol": "TEST", "probability": 0.4}], horizon_sessions=5,
            base_rates={"__default__": 0.1}, path=self.path,
        )
        self.assertEqual(first["predictionsAppended"], 1)
        second = shadow_journal.record_shadow_predictions(
            "big-move", "1", "2026-01-05",
            [{"symbol": "TEST", "probability": 0.99}], horizon_sessions=5, path=self.path,
        )
        self.assertEqual(second["predictionsAppended"], 0)
        self.assertEqual(second["duplicatesRefused"], 1)
        stored = shadow_journal._load(self.path)
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0]["probability"], 0.4)
        self.assertTrue(stored[0]["predictionHash"])

    def test_daily_alert_budget_is_enforced(self) -> None:
        predictions = [{"symbol": f"AA{index:02d}", "probability": 0.9} for index in range(9)]
        result = shadow_journal.record_shadow_predictions(
            "big-move", "1", "2026-01-05", predictions, horizon_sessions=5,
            base_rates={"__default__": 0.05}, path=self.path,
        )
        self.assertEqual(result["alerts"], shadow_journal.MAX_DAILY_ALERTS)

    def test_a_shadow_model_never_reaches_research_alert(self) -> None:
        shadow_journal.record_shadow_predictions(
            "big-move", "1", "2026-01-05", [{"symbol": "TEST", "probability": 0.95}],
            horizon_sessions=5, base_rates={"__default__": 0.05}, path=self.path,
        )
        statuses = {row["alertStatus"] for row in shadow_journal._load(self.path)}
        self.assertNotIn("research_alert", statuses)
        self.assertIn("early_watch", statuses)

    def test_promotion_gates_fail_on_a_thin_record(self) -> None:
        shadow_journal.record_shadow_predictions(
            "big-move", "1", "2026-01-05", [{"symbol": "TEST", "probability": 0.4}],
            horizon_sessions=5, path=self.path,
        )
        report = shadow_journal.promotion_metrics("big-move", path=self.path)
        self.assertFalse(report["promotable"])
        self.assertTrue(any("60 shadow trading sessions" in failure for failure in report["gateFailures"]))
        self.assertIn("stays in shadow", report["decision"])

    def test_human_acceptance_is_required_even_with_perfect_numbers(self) -> None:
        report = shadow_journal.promotion_metrics("absent-model", path=self.path)
        self.assertIn(
            "Worst loss, false alerts and missing data have not been accepted by Luke",
            report["gateFailures"],
        )


if __name__ == "__main__":
    unittest.main()
