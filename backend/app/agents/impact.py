"""Feature & location impact analysis: a log-linear hedonic regression fitted
once over the dataset. Coefficients become elasticities a human can quote:
"each quality point adds ~X %", "this neighborhood carries a Y % premium"."""
from __future__ import annotations

import numpy as np

from app.data.loader import Dataset, NEIGHBORHOOD_NAMES
from app.schemas import ImpactFactor


class ImpactModel:
    def __init__(self, ds: Dataset):
        f = ds.frame
        nbs = sorted(f["neighborhood"].unique())
        self.nbs = nbs
        cols = [
            np.ones(len(f)),
            f["overallQual"].values.astype(float),
            np.log(f["grLivArea"].clip(lower=100).values.astype(float)),
            f["yearBuilt"].values.astype(float),
            f["garageCars"].values.astype(float),
            f["totalBsmtSF"].values.astype(float) / 500.0,
            np.log(f["lotArea"].clip(lower=500).values.astype(float)),
            f["overallCond"].values.astype(float),
        ]
        for nb in nbs[1:]:  # first neighborhood is the reference level
            cols.append((f["neighborhood"].values == nb).astype(float))
        X = np.column_stack(cols)
        y = np.log(f["salePrice"].values.astype(float))
        beta, *_ = np.linalg.lstsq(X, y, rcond=None)
        self.b = {"qual": beta[1], "area": beta[2], "year": beta[3], "garage": beta[4], "bsmt": beta[5], "lot": beta[6], "cond": beta[7]}
        self.nb_fe = {nbs[0]: 0.0} | {nb: float(beta[8 + i]) for i, nb in enumerate(nbs[1:])}
        self.nb_fe_median = float(np.median(list(self.nb_fe.values())))
        resid = y - X @ beta
        self.r2 = float(1 - resid.var() / y.var())

    def neighborhood_premium(self, nb: str) -> float:
        return float(np.exp(self.nb_fe.get(nb, self.nb_fe_median) - self.nb_fe_median) - 1)

    def factors(self, subject) -> list[ImpactFactor]:
        b = self.b
        area = max(subject.grLivArea, 300)
        per100 = float(np.exp(b["area"] * np.log((area + 100) / area)) - 1)
        prem = self.neighborhood_premium(subject.neighborhood)
        name = NEIGHBORHOOD_NAMES.get(subject.neighborhood, subject.neighborhood)
        return [
            ImpactFactor(feature="OverallQual", elasticity=round(float(np.exp(b["qual"]) - 1), 4), description=f"Each quality point adds ~{(np.exp(b['qual']) - 1) * 100:.1f}% to expected price — the strongest single driver after location."),
            ImpactFactor(feature="Neighborhood", elasticity=round(abs(prem), 4), description=f"{name} carries a {'premium' if prem >= 0 else 'discount'} of {abs(prem) * 100:.0f}% relative to the typical Ames neighborhood, holding size, age and quality constant."),
            ImpactFactor(feature="GrLivArea", elasticity=round(per100, 4), description=f"At {subject.grLivArea:,} sq ft, every additional 100 sq ft above grade adds ~{per100 * 100:.1f}%; the effect diminishes with size (log-linear)."),
            ImpactFactor(feature="YearBuilt", elasticity=round(float(np.exp(b['year'] * 10) - 1), 4), description=f"Newer construction commands ~{(np.exp(b['year'] * 10) - 1) * 100:.1f}% per decade after controlling for quality and size."),
            ImpactFactor(feature="GarageCars", elasticity=round(float(np.exp(b['garage']) - 1), 4), description=f"Each garage bay adds ~{(np.exp(b['garage']) - 1) * 100:.1f}%."),
            ImpactFactor(feature="TotalBsmtSF", elasticity=round(float(np.exp(b['bsmt']) - 1), 4), description=f"Basement area contributes ~{(np.exp(b['bsmt']) - 1) * 100:.1f}% per 500 sq ft."),
            ImpactFactor(feature="OverallCond", elasticity=round(float(np.exp(b['cond']) - 1), 4), description=f"Condition adds ~{(np.exp(b['cond']) - 1) * 100:.1f}% per point — smaller than quality because condition is partly priced into age."),
        ]
