from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class CandidateModel:
    estimator: object

    def rank(self, frame: pd.DataFrame) -> tuple[tuple[str, float], ...]:
        estimator = self.estimator
        if hasattr(estimator, "predict_proba"):
            probabilities = estimator.predict_proba(frame)[0]
            classes = list(estimator.classes_)
            order = np.argsort(probabilities)[::-1]
            return tuple((str(classes[i]), float(probabilities[i])) for i in order)
        predicted = str(estimator.predict(frame)[0])
        return ((predicted, 1.0),)


def train_tpot(features: pd.DataFrame, labels: pd.Series) -> CandidateModel:
    from tpot import TPOTClassifier

    model = TPOTClassifier(
        search_space="linear-light",
        scorers=["balanced_accuracy"],
        cv=2,
        population_size=3,
        generations=1,
        max_time_mins=1,
        max_eval_time_mins=0.25,
        n_jobs=1,
        processes=False,
        validation_strategy="none",
        random_state=42,
        verbose=0,
    )
    model.fit(features, labels)
    return CandidateModel(model)
