"""Interpretable challengers and the incumbent base-rate champion.

Kestrel has no promoted statistical model, so the honest incumbent for the
research questions is the **base rate**: the observed frequency of the event in
the training window. A challenger that cannot beat that has learned nothing.

The challenger is a regularised logistic regression, chosen because its
coefficients can be read and argued with. It is fitted by gradient descent on
standardised features, with L2 shrinkage, and the probability calibrator is fit
on a separate, later slice of the training window — never on the data the model
was fitted to, and never on the test period.

Nothing here reads the archive, decides eligibility or produces a
recommendation. It maps a feature vector to a probability and nothing else.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

from feature_store import FEATURE_NAMES


MODEL_FAMILY = "regularised-logistic"
CHALLENGER_VERSION = "2026.08.1"
CHAMPION_VERSION = "base-rate-2026.08.1"

DEFAULT_L2 = 1.0
DEFAULT_LEARNING_RATE = 0.1
DEFAULT_EPOCHS = 400
CALIBRATION_FRACTION = 0.25
MIN_CALIBRATION_ROWS = 50


def _solve(matrix: Sequence[Sequence[float]], vector: Sequence[float]) -> Optional[List[float]]:
    """Gaussian elimination with partial pivoting; None when singular."""
    size = len(vector)
    augmented = [list(matrix[row]) + [vector[row]] for row in range(size)]
    for column in range(size):
        pivot = max(range(column, size), key=lambda row: abs(augmented[row][column]))
        if abs(augmented[pivot][column]) < 1e-12:
            return None
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        divisor = augmented[column][column]
        for index in range(column, size + 1):
            augmented[column][index] /= divisor
        for row in range(size):
            if row == column:
                continue
            factor = augmented[row][column]
            if factor:
                for index in range(column, size + 1):
                    augmented[row][index] -= factor * augmented[column][index]
    return [augmented[row][size] for row in range(size)]


def _sigmoid(value: float) -> float:
    if value >= 0:
        return 1 / (1 + math.exp(-min(30.0, value)))
    exponent = math.exp(max(-30.0, value))
    return exponent / (1 + exponent)


class BaseRateChampion:
    """The incumbent: predict the training-window frequency for everyone."""

    version = CHAMPION_VERSION
    family = "base-rate"

    def __init__(self) -> None:
        self.rate: Optional[float] = None
        self.trained_rows = 0

    def fit(self, rows: Sequence[Dict[str, Any]], label_key: str) -> "BaseRateChampion":
        labels = [int(row[label_key]) for row in rows]
        self.rate = (sum(labels) / len(labels)) if labels else None
        self.trained_rows = len(labels)
        return self

    def predict(self, row: Dict[str, Any]) -> Optional[float]:
        return self.rate

    def describe(self) -> Dict[str, Any]:
        return {
            "version": self.version, "family": self.family,
            "rate": round(self.rate, 6) if self.rate is not None else None,
            "trainedRows": self.trained_rows,
            "explanation": "Predicts the training-window event frequency for every security.",
        }


class LogisticChallenger:
    """Regularised logistic regression with a separately fitted calibrator."""

    version = CHALLENGER_VERSION
    family = MODEL_FAMILY

    def __init__(self, feature_names: Sequence[str] = FEATURE_NAMES,
                 l2: float = DEFAULT_L2, learning_rate: float = DEFAULT_LEARNING_RATE,
                 epochs: int = DEFAULT_EPOCHS) -> None:
        self.feature_names = list(feature_names)
        self.l2 = l2
        self.learning_rate = learning_rate
        self.epochs = epochs
        self.weights: List[float] = []
        self.bias = 0.0
        self.means: List[float] = []
        self.deviations: List[float] = []
        self.calibrator: Optional[Tuple[float, float]] = None
        self.trained_rows = 0
        self.calibration_rows = 0

    # -- fitting --------------------------------------------------------

    def _standardise(self, vector: Sequence[float]) -> List[float]:
        return [
            (value - mean) / deviation if deviation else 0.0
            for value, mean, deviation in zip(vector, self.means, self.deviations)
        ]

    def _raw_probability(self, vector: Sequence[float]) -> float:
        standardised = self._standardise(vector)
        total = self.bias + sum(weight * value for weight, value in zip(self.weights, standardised))
        return _sigmoid(total)

    def fit(self, rows: Sequence[Dict[str, Any]], label_key: str,
            vector_key: str = "vector") -> "LogisticChallenger":
        """Fit weights on the earlier part of the window, calibrate on the later part."""
        usable = [row for row in rows if row.get(vector_key)]
        if not usable:
            self.trained_rows = 0
            return self
        usable = sorted(usable, key=lambda row: row.get("sessionDate", ""))

        split = len(usable) - int(len(usable) * CALIBRATION_FRACTION)
        if len(usable) - split < MIN_CALIBRATION_ROWS:
            split = len(usable)
        fit_rows = usable[:split]
        calibration_rows = usable[split:]

        vectors = [list(row[vector_key]) for row in fit_rows]
        labels = [int(row[label_key]) for row in fit_rows]
        width = len(self.feature_names)
        self.means = [sum(vector[index] for vector in vectors) / len(vectors) for index in range(width)]
        self.deviations = []
        for index in range(width):
            mean = self.means[index]
            variance = sum((vector[index] - mean) ** 2 for vector in vectors) / max(1, len(vectors) - 1)
            self.deviations.append(math.sqrt(variance) or 1.0)

        standardised = [self._standardise(vector) for vector in vectors]
        self._fit_weights(standardised, labels, width)

        self.trained_rows = len(fit_rows)
        self.calibration_rows = len(calibration_rows)
        self.calibrator = None
        if len(calibration_rows) >= MIN_CALIBRATION_ROWS:
            self._fit_calibrator(calibration_rows, label_key, vector_key)
        return self

    def _fit_weights(self, vectors: Sequence[Sequence[float]], labels: Sequence[int],
                     width: int) -> None:
        """Penalised Newton steps. Exact enough to converge in a handful of passes.

        Gradient descent needs thousands of passes to settle on a rare-event
        problem, and an unconverged model looks like a model with no signal. With
        eleven features the Newton system is tiny, so solving it directly is both
        faster and honest about what the model can actually fit.
        """
        parameters = [0.0] * (width + 1)  # index 0 is the intercept
        for _ in range(self.epochs if self.epochs < 50 else 25):
            gradient = [0.0] * (width + 1)
            hessian = [[0.0] * (width + 1) for _ in range(width + 1)]
            for vector, label in zip(vectors, labels):
                row = [1.0] + list(vector)
                total = sum(parameter * value for parameter, value in zip(parameters, row))
                prediction = _sigmoid(total)
                error = prediction - label
                weight = max(prediction * (1 - prediction), 1e-9)
                for index in range(width + 1):
                    gradient[index] += error * row[index]
                    for column in range(index, width + 1):
                        hessian[index][column] += weight * row[index] * row[column]
            for index in range(width + 1):
                for column in range(index):
                    hessian[index][column] = hessian[column][index]
            # Shrink the slopes, never the intercept: the base rate must stay free.
            for index in range(1, width + 1):
                gradient[index] += self.l2 * parameters[index]
                hessian[index][index] += self.l2

            step = _solve(hessian, gradient)
            if step is None:
                break
            parameters = [parameter - move for parameter, move in zip(parameters, step)]
            if max(abs(move) for move in step) < 1e-8:
                break
        self.bias = parameters[0]
        self.weights = parameters[1:]

    def _fit_calibrator(self, rows: Sequence[Dict[str, Any]], label_key: str, vector_key: str) -> None:
        """Platt scaling on a later slice the weights never saw."""
        points = []
        for row in rows:
            probability = self._raw_probability(row[vector_key])
            clipped = min(1 - 1e-6, max(1e-6, probability))
            points.append((math.log(clipped / (1 - clipped)), int(row[label_key])))
        if len({label for _, label in points}) < 2:
            return
        intercept, slope = 0.0, 1.0
        for _ in range(200):
            gradient_intercept = gradient_slope = 0.0
            for logit, label in points:
                prediction = _sigmoid(intercept + slope * logit)
                error = prediction - label
                gradient_intercept += error
                gradient_slope += error * logit
            intercept -= 0.1 * gradient_intercept / len(points)
            slope -= 0.1 * gradient_slope / len(points)
        self.calibrator = (intercept, slope)

    # -- prediction -----------------------------------------------------

    def predict(self, row: Dict[str, Any], vector_key: str = "vector") -> Optional[float]:
        vector = row.get(vector_key)
        if not vector or not self.weights or len(vector) != len(self.weights):
            return None
        probability = self._raw_probability(vector)
        if self.calibrator:
            intercept, slope = self.calibrator
            clipped = min(1 - 1e-6, max(1e-6, probability))
            probability = _sigmoid(intercept + slope * math.log(clipped / (1 - clipped)))
        return probability

    def describe(self) -> Dict[str, Any]:
        coefficients = {
            name: round(weight, 5) for name, weight in zip(self.feature_names, self.weights)
        }
        ranked = sorted(coefficients.items(), key=lambda item: -abs(item[1]))
        return {
            "version": self.version,
            "family": self.family,
            "l2": self.l2,
            "trainedRows": self.trained_rows,
            "calibrationRows": self.calibration_rows,
            "calibrated": bool(self.calibrator),
            "coefficients": coefficients,
            "strongestFeatures": [name for name, _ in ranked[:3]],
            "explanation": (
                "Standardised logistic regression with L2 shrinkage. Coefficients are on "
                "standardised features, so they compare directly with one another."
            ),
        }


def ablate(feature_names: Sequence[str], removed: str) -> List[str]:
    """Feature list with one family removed, for ablation studies."""
    return [name for name in feature_names if name != removed]
