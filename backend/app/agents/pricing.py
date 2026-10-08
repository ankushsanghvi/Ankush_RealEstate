"""Price prediction model: gradient-boosted trees on log(SalePrice).

Trained once at startup (≈2 s) and cached by data hash. Honest error metrics
come from 5-fold cross-validation, not from the training fit. Feature
contributions use single-feature substitution against the dataset median
(a cheap, model-agnostic attribution — "SHAP-lite")."""
from __future__ import annotations

import hashlib
import json
import logging
import pickle
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.model_selection import KFold

from app.data.loader import Dataset, FEATURES
from app.schemas import FeatureContribution, PricePrediction

log = logging.getLogger(__name__)
MODEL_NAME = "HistGradientBoosting · v1 (log-target, 5-fold CV)"
LABELS = {
    "overallQual": "OverallQual", "overallCond": "OverallCond", "grLivArea": "GrLivArea", "totalBsmtSF": "TotalBsmtSF",
    "garageCars": "GarageCars", "garageArea": "GarageArea", "yearBuilt": "YearBuilt", "yearRemodAdd": "YearRemodAdd",
    "fullBath": "FullBath", "bedroomAbvGr": "BedroomAbvGr", "totRmsAbvGrd": "TotRmsAbvGrd", "lotArea": "LotArea",
    "nbPpsf": "Neighborhood", "nbMedian": "Neighborhood median",
}


class PricingModel:
    def __init__(self, ds: Dataset, cache_dir: Path):
        self.ds = ds
        self.cols = FEATURES + ["nbPpsf", "nbMedian"]
        X, y = self._design(ds.frame)
        key = hashlib.sha1(pd.util.hash_pandas_object(ds.frame).values.tobytes()).hexdigest()[:12]
        path = cache_dir / f"gbm_{key}.pkl"
        if path.exists():
            with open(path, "rb") as f:
                self.model, self.metrics = pickle.load(f)
        else:
            self.model, self.metrics = self._train(X, y)
            with open(path, "wb") as f:
                pickle.dump((self.model, self.metrics), f)
        self.medians = {c: float(np.median(X[:, i])) for i, c in enumerate(self.cols)}
        log.info("pricing model ready: %s", json.dumps(self.metrics))

    def _design(self, frame: pd.DataFrame):
        st = self.ds.neighborhood_stats
        X = frame[FEATURES].astype(float).copy()
        X["nbPpsf"] = frame["neighborhood"].map(lambda n: st.get(n, {}).get("ppsf_median", 100.0))
        X["nbMedian"] = frame["neighborhood"].map(lambda n: st.get(n, {}).get("median", 160000))
        return X.values, np.log(frame["salePrice"].values)

    def _make(self):
        return HistGradientBoostingRegressor(max_iter=600, learning_rate=0.05, max_leaf_nodes=31, min_samples_leaf=15, l2_regularization=0.5, random_state=0)

    def _train(self, X, y):
        kf = KFold(5, shuffle=True, random_state=0)
        preds = np.zeros_like(y)
        for tr, te in kf.split(X):
            m = self._make().fit(X[tr], y[tr])
            preds[te] = m.predict(X[te])
        resid = y - preds
        mape = float(np.mean(np.abs(np.expm1(preds - y))))  # |exp(pred)/exp(y) - 1|
        r2 = float(1 - np.sum(resid ** 2) / np.sum((y - y.mean()) ** 2))
        sigma = float(np.std(resid))
        model = self._make().fit(X, y)
        return model, {"mape": round(mape, 4), "r2": round(r2, 4), "sigma_log": round(sigma, 4), "n": int(len(y))}

    def _row(self, subject) -> np.ndarray:
        st = self.ds.neighborhood_stats.get(subject.neighborhood, {})
        vals = {
            "overallQual": subject.overallQual, "overallCond": 5, "grLivArea": subject.grLivArea, "totalBsmtSF": subject.totalBsmtSF,
            "garageCars": subject.garageCars, "garageArea": subject.garageCars * 260, "yearBuilt": subject.yearBuilt,
            "yearRemodAdd": max(subject.yearBuilt, 1950), "fullBath": subject.fullBath, "bedroomAbvGr": subject.bedrooms,
            "totRmsAbvGrd": subject.bedrooms + 3, "lotArea": subject.lotArea,
            "nbPpsf": st.get("ppsf_median", 100.0), "nbMedian": st.get("median", 160000),
        }
        return np.array([[float(vals[c]) for c in self.cols]])

    def predict(self, subject) -> PricePrediction:
        x = self._row(subject)
        log_pred = float(self.model.predict(x)[0])
        pred = float(np.exp(log_pred))
        sigma = self.metrics["sigma_log"]
        contribs: list[FeatureContribution] = []
        for i, c in enumerate(self.cols):
            if c == "nbMedian":
                continue  # the two neighborhood columns are one concept; attribute to nbPpsf
            x2 = x.copy()
            x2[0, i] = self.medians[c]
            if c == "nbPpsf":
                x2[0, self.cols.index("nbMedian")] = self.medians["nbMedian"]
            delta = pred - float(np.exp(self.model.predict(x2)[0]))
            contribs.append(FeatureContribution(feature=LABELS[c], impact=int(round(delta))))
        contribs.sort(key=lambda c: -abs(c.impact))
        return PricePrediction(
            model=MODEL_NAME, prediction=int(round(pred / 500) * 500),
            low=int(round(np.exp(log_pred - 1.645 * sigma) / 500) * 500), high=int(round(np.exp(log_pred + 1.645 * sigma) / 500) * 500),
            mape=self.metrics["mape"], r2=self.metrics["r2"], featureContributions=contribs[:8],
        )
