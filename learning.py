"""The recursive learning loop: build, validate, gate, register.

This runs the research comparison end to end and returns a verdict. It never
changes a live recommendation. Promotion is a separate, human decision recorded
in ``model_registry``; the most this module can conclude is that a challenger
has earned a shadow run.

Order of operations matches the roadmap's exact learning loop: freeze the
information set, build versioned features, predict with champion and challenger,
mature outcomes independently, validate chronologically with purging, calibrate
on a separate slice, then check every gate before anything is registered.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from challenger import BaseRateChampion, LogisticChallenger
from feature_store import FEATURE_NAMES, FeatureStore, build_features, feature_vector, research_eligible
from learning_dataset import (
    DATASET_VERSION,
    HORIZON_THRESHOLDS,
    build_dataset,
    dataset_summary,
    subset_vectors,
)
from model_registry import register_experiment, registry_summary
from outcome_source import DEFAULT_DATABASE, OutcomeSource
from shadow_journal import promotion_metrics, record_shadow_predictions, shadow_summary
from validation import (
    DEFAULT_OUTER_PERIODS,
    apply_split,
    leakage_violations,
    score_predictions,
    walk_forward_splits,
)


QUESTIONS = {
    "bigMove": {
        "label": "bigMove",
        "description": "Probability of an unusually large benchmark-relative move, either direction.",
    },
    "direction": {
        "label": "up",
        "description": "Probability of outperforming the benchmark beyond the declared cost band.",
    },
}

# Statistical gate: the challenger must beat the champion in most outer periods
# with an interval that excludes zero improvement.
MIN_WINNING_FOLDS = 4
MIN_FOLDS_REQUIRED = 5
MIN_TEST_ROWS_PER_FOLD = 30
CALIBRATION_SLOPE_RANGE = (0.8, 1.2)
MAX_CALIBRATION_ERROR = 0.05
MIN_BRIER_SKILL = 0.0


def _fold_result(question: str, label_key: str, train: List[Dict[str, Any]],
                 test: List[Dict[str, Any]], fold: Dict[str, Any],
                 feature_names: Sequence[str]) -> Optional[Dict[str, Any]]:
    """Fit both models on one fold and score them on the untouched test period."""
    violations = leakage_violations(train, test)
    if violations:
        return {"fold": fold["fold"], "status": "leakage", "violations": violations}
    if len(test) < MIN_TEST_ROWS_PER_FOLD or len(train) < MIN_TEST_ROWS_PER_FOLD:
        return {"fold": fold["fold"], "status": "insufficient",
                "trainRows": len(train), "testRows": len(test)}
    if len({row[label_key] for row in train}) < 2:
        return {"fold": fold["fold"], "status": "single-class-training"}

    champion = BaseRateChampion().fit(train, label_key)
    challenger = LogisticChallenger(feature_names=feature_names).fit(train, label_key)

    champion_rows, challenger_rows = [], []
    for row in test:
        champion_probability = champion.predict(row)
        challenger_probability = challenger.predict(row)
        if champion_probability is None or challenger_probability is None:
            continue
        common = {"sessionDate": row["sessionDate"], "label": row[label_key], "ticker": row["ticker"]}
        champion_rows.append({**common, "probability": champion_probability})
        challenger_rows.append({**common, "probability": challenger_probability})
    if not challenger_rows:
        return {"fold": fold["fold"], "status": "no-predictions"}

    reference = champion.rate
    champion_score = score_predictions(champion_rows, reference_rate=reference)
    challenger_score = score_predictions(challenger_rows, reference_rate=reference)
    improvement = (champion_score["brier"] or 0) - (challenger_score["brier"] or 0)
    interval = challenger_score["brierSkillInterval"]
    beats = bool(
        improvement > 0
        and interval.get("lower95") is not None
        and interval["lower95"] > 0
    )
    return {
        "fold": fold["fold"],
        "status": "scored",
        "trainStart": fold["trainStart"], "trainEnd": fold["trainEnd"],
        "testStart": fold["testStart"], "testEnd": fold["testEnd"],
        "trainRows": len(train), "testRows": len(test), "purgedRows": fold.get("purgedRows", 0),
        "champion": champion_score,
        "challenger": challenger_score,
        "brierImprovement": round(improvement, 6),
        "challengerWins": beats,
        "challengerModel": challenger.describe(),
    }


def _gate_failures(scored: List[Dict[str, Any]], summary: Dict[str, Any]) -> List[str]:
    """Every reason this challenger may not proceed to a shadow run."""
    failures: List[str] = []
    if len(scored) < MIN_FOLDS_REQUIRED:
        failures.append(
            f"Only {len(scored)} scored walk-forward periods; at least {MIN_FOLDS_REQUIRED} are required"
        )
    wins = sum(1 for fold in scored if fold["challengerWins"])
    if wins < MIN_WINNING_FOLDS:
        failures.append(
            f"Challenger beat the champion in {wins} of {len(scored)} periods; {MIN_WINNING_FOLDS} are required"
        )

    calibrations = [fold["challenger"]["calibration"]["slope"] for fold in scored]
    usable = [slope for slope in calibrations if slope is not None]
    if not usable:
        failures.append("Calibration slope could not be estimated in any period")
    else:
        low, high = CALIBRATION_SLOPE_RANGE
        outside = [slope for slope in usable if not low <= slope <= high]
        if len(outside) > len(usable) / 2:
            failures.append(
                f"Calibration slope sits outside {low}-{high} in most periods (worst {min(usable):.2f})"
            )
    errors = [fold["challenger"]["expectedCalibrationError"] for fold in scored
              if fold["challenger"]["expectedCalibrationError"] is not None]
    if errors and max(errors) > MAX_CALIBRATION_ERROR:
        failures.append(
            f"Calibration error reaches {max(errors):.3f}, above the {MAX_CALIBRATION_ERROR} limit"
        )
    skills = [fold["challenger"]["brierSkill"] for fold in scored
              if fold["challenger"]["brierSkill"] is not None]
    if skills and min(skills) <= MIN_BRIER_SKILL:
        failures.append(f"Brier skill falls to {min(skills):.3f} in the weakest period")

    if not summary.get("rows"):
        failures.append("The research dataset is empty")
    if summary.get("securities", 0) < 2:
        failures.append("Fewer than two securities in the research dataset")
    return failures


def run_experiment(question: str = "bigMove", horizon: int = 5,
                   database: Path = DEFAULT_DATABASE,
                   outer_periods: int = DEFAULT_OUTER_PERIODS,
                   feature_names: Sequence[str] = FEATURE_NAMES,
                   register: bool = True, notes: str = "") -> Dict[str, Any]:
    """Full chronological comparison for one question at one horizon."""
    if question not in QUESTIONS:
        raise ValueError(f"Question must be one of {sorted(QUESTIONS)}")
    label_key = QUESTIONS[question]["label"]

    rows = build_dataset(horizon, database=database)
    if list(feature_names) != list(FEATURE_NAMES):
        rows = subset_vectors(rows, feature_names)
    summary = dataset_summary(rows, horizon)

    folds = walk_forward_splits(
        [row["sessionDate"] for row in rows], horizon_sessions=horizon,
        outer_periods=outer_periods,
    )
    results: List[Dict[str, Any]] = []
    for fold in folds:
        train, test = apply_split(rows, fold)
        outcome = _fold_result(question, label_key, train, test, fold, feature_names)
        if outcome:
            results.append(outcome)
    scored = [fold for fold in results if fold["status"] == "scored"]
    failures = _gate_failures(scored, summary)
    verdict = "passed" if not failures else "failed"

    champion_summary = {
        "version": BaseRateChampion.version, "family": "base-rate",
        "averageBrier": _average([fold["champion"]["brier"] for fold in scored]),
    }
    challenger_summary = {
        "version": LogisticChallenger.version, "family": LogisticChallenger.family,
        "features": list(feature_names),
        "averageBrier": _average([fold["challenger"]["brier"] for fold in scored]),
        "averageBrierSkill": _average([fold["challenger"]["brierSkill"] for fold in scored]),
        "winningFolds": sum(1 for fold in scored if fold["challengerWins"]),
    }

    experiment = {
        "question": question,
        "questionDescription": QUESTIONS[question]["description"],
        "horizonSessions": horizon,
        "bigMoveThreshold": HORIZON_THRESHOLDS.get(horizon),
        "dataset": summary,
        "folds": results,
        "scoredFolds": len(scored),
        "champion": champion_summary,
        "challenger": challenger_summary,
        "gateFailures": failures,
        "verdict": verdict,
        "outcome": (
            "The challenger may begin a shadow run. It still cannot influence a live "
            "recommendation until the shadow period and human approval are complete."
            if verdict == "passed" else
            "The challenger stays in research. No live recommendation changes."
        ),
    }
    if register:
        register_experiment(
            name=f"{question}-h{horizon}-{DATASET_VERSION}",
            question=question, horizon_sessions=horizon,
            champion=champion_summary, challenger=challenger_summary,
            folds=[{key: fold.get(key) for key in
                    ("fold", "status", "testStart", "testEnd", "testRows", "purgedRows",
                     "brierImprovement", "challengerWins")} for fold in results],
            verdict=verdict, gate_failures=failures, dataset=summary, notes=notes,
        )
    return experiment


def _average(values: Sequence[Optional[float]]) -> Optional[float]:
    usable = [value for value in values if value is not None]
    return round(sum(usable) / len(usable), 6) if usable else None


def ablation_study(question: str = "bigMove", horizon: int = 5,
                   database: Path = DEFAULT_DATABASE) -> Dict[str, Any]:
    """Prove which feature families actually add value, one removal at a time."""
    full = run_experiment(question, horizon, database=database, register=False)
    baseline = full["challenger"]["averageBrier"]
    removals = []
    for name in FEATURE_NAMES:
        reduced = [feature for feature in FEATURE_NAMES if feature != name]
        result = run_experiment(question, horizon, database=database,
                                feature_names=reduced, register=False)
        without = result["challenger"]["averageBrier"]
        removals.append({
            "removed": name,
            "averageBrierWithout": without,
            "harmWhenRemoved": (
                round(without - baseline, 6) if baseline is not None and without is not None else None
            ),
        })
    removals.sort(key=lambda item: -(item["harmWhenRemoved"] or 0))
    return {
        "question": question,
        "horizonSessions": horizon,
        "averageBrierWithAllFeatures": baseline,
        "removals": removals,
        "reading": "A positive harm value means the score got worse without that feature.",
    }


def run_shadow_session(question: str = "bigMove", horizon: int = 5,
                       database: Path = DEFAULT_DATABASE,
                       model_id: str = "big-move-logistic",
                       session_date: Optional[str] = None) -> Dict[str, Any]:
    """Predict forward for the latest archived session, without showing anything.

    The model is refitted on every row that had fully matured by the training
    cutoff, then asked about securities whose outcome is still unknown. Those
    predictions are frozen immediately, so they can never be revised once the
    result is visible.
    """
    label_key = QUESTIONS[question]["label"]
    rows = build_dataset(horizon, database=database)
    store = FeatureStore(database)
    open_rows = _open_predictions(store, horizon, session_date)
    if not rows or not open_rows:
        return {
            "status": "not-ready",
            "modelId": model_id,
            "trainingRows": len(rows),
            "openPredictions": len(open_rows),
            "message": (
                "The archive cannot both train a model and leave open predictions yet. "
                "No shadow prediction was recorded."
            ),
        }

    target_date = open_rows[0]["sessionDate"]
    training = [row for row in rows if row["exitDate"] < target_date]
    if len({row[label_key] for row in training}) < 2 or len(training) < MIN_TEST_ROWS_PER_FOLD:
        return {"status": "not-ready", "modelId": model_id, "trainingRows": len(training),
                "message": "Too little matured history to fit a shadow model."}

    challenger = LogisticChallenger().fit(training, label_key)
    rate = BaseRateChampion().fit(training, label_key).rate
    predictions = []
    for row in open_rows:
        probability = challenger.predict(row)
        if probability is None:
            continue
        predictions.append({"symbol": row["ticker"], "probability": probability,
                            "evidenceClean": True})
    recorded = record_shadow_predictions(
        model_id=model_id, model_version=LogisticChallenger.version,
        session_date=target_date, predictions=predictions,
        horizon_sessions=horizon, base_rates={"__default__": rate},
    )
    return {
        "status": "recorded",
        "modelId": model_id,
        "sessionDate": target_date,
        "trainingRows": len(training),
        "baseRate": round(rate, 6) if rate is not None else None,
        "model": challenger.describe(),
        **recorded,
        "visibility": "Shadow only. Nothing here changes a displayed action or rating.",
    }


def _open_predictions(store: FeatureStore, horizon: int,
                      session_date: Optional[str]) -> List[Dict[str, Any]]:
    """Feature rows for the latest session whose outcome is not yet known."""
    candidates: List[Dict[str, Any]] = []
    for history in store.iter_histories():
        if history.ticker == "SPY" or not len(history):
            continue
        index = len(history) - 1
        if session_date:
            if session_date not in history.dates:
                continue
            index = history.dates.index(session_date)
        if not research_eligible(history, index)["eligible"]:
            continue
        features = build_features(history, index)
        vector = feature_vector(features)
        if vector is None:
            continue
        candidates.append({
            "ticker": history.ticker, "securityId": history.security_id,
            "sessionDate": history.dates[index], "features": features["values"], "vector": vector,
        })
    if not candidates:
        return []
    latest = max(row["sessionDate"] for row in candidates)
    return [row for row in candidates if row["sessionDate"] == latest]


def learning_status(database: Path = DEFAULT_DATABASE) -> Dict[str, Any]:
    """What the learning system can honestly say right now."""
    coverage = OutcomeSource(database).coverage()
    registry = registry_summary()
    ready = coverage["status"] == "ready"
    return {
        "datasetVersion": DATASET_VERSION,
        "archive": coverage,
        "registry": registry,
        "shadow": shadow_summary(),
        "questions": {name: value["description"] for name, value in QUESTIONS.items()},
        "horizons": sorted(HORIZON_THRESHOLDS),
        "champion": (
            "Your ratings come from the approved rule-based score. In research, a challenger "
            "must first beat the plain base rate, and none has been promoted."
        ),
        "liveInfluence": registry["liveInfluence"],
        "status": "ready" if ready else "waiting-for-archive",
        "message": (
            "The archive is available; research experiments can run."
            if ready else
            "No adjusted market-history archive is present, so no model can be trained or scored."
        ),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Kestrel recursive learning research runner")
    parser.add_argument(
        "command",
        choices=["status", "experiment", "ablation", "registry", "shadow", "gates", "risk"],
    )
    parser.add_argument("--question", default="bigMove", choices=sorted(QUESTIONS))
    parser.add_argument("--horizon", type=int, default=5, choices=sorted(HORIZON_THRESHOLDS))
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument("--periods", type=int, default=DEFAULT_OUTER_PERIODS)
    parser.add_argument("--model", default="big-move-logistic")
    parser.add_argument("--no-register", action="store_true")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "status":
        print(json.dumps(learning_status(args.database), indent=2, sort_keys=True))
    elif args.command == "registry":
        print(json.dumps(registry_summary(), indent=2, sort_keys=True))
    elif args.command == "ablation":
        print(json.dumps(ablation_study(args.question, args.horizon, args.database),
                         indent=2, sort_keys=True))
    elif args.command == "shadow":
        print(json.dumps(run_shadow_session(args.question, args.horizon, args.database),
                         indent=2, sort_keys=True))
    elif args.command == "gates":
        print(json.dumps(promotion_metrics(args.model), indent=2, sort_keys=True))
    elif args.command == "risk":
        from model_risk import model_risk_report
        print(json.dumps(model_risk_report(args.model, args.horizon, args.database),
                         indent=2, sort_keys=True))
    else:
        result = run_experiment(
            args.question, args.horizon, database=args.database,
            outer_periods=args.periods, register=not args.no_register,
        )
        print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
