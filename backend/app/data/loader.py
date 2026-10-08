"""Load the Ames Housing ARFF (OpenML id 43926) into typed records plus a
natural-language "property case" per row that the retrieval layer indexes."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from app.schemas import Property

QUAL_MAP = {
    "Very_Poor": 1, "Poor": 2, "Fair": 3, "Below_Average": 4, "Average": 5,
    "Above_Average": 6, "Good": 7, "Very_Good": 8, "Excellent": 9, "Very_Excellent": 10,
}

# OpenML long names → canonical Ames codes used in the literature & the UI.
NEIGHBORHOOD_CODES = {
    "North_Ames": "NAmes", "College_Creek": "CollgCr", "Old_Town": "OldTown", "Edwards": "Edwards",
    "Somerset": "Somerst", "Northridge_Heights": "NridgHt", "Gilbert": "Gilbert", "Sawyer": "Sawyer",
    "Northwest_Ames": "NWAmes", "Sawyer_West": "SawyerW", "Mitchell": "Mitchel", "Brookside": "BrkSide",
    "Crawford": "Crawfor", "Iowa_DOT_and_Rail_Road": "IDOTRR", "Timberland": "Timber", "Northridge": "NoRidge",
    "Stone_Brook": "StoneBr", "South_and_West_of_Iowa_State_University": "SWISU", "Clear_Creek": "ClearCr",
    "Meadow_Village": "MeadowV", "Briardale": "BrDale", "Bloomington_Heights": "Blmngtn", "Veenker": "Veenker",
    "Northpark_Villa": "NPkVill", "Blueste": "Blueste", "Greens": "Greens", "Green_Hills": "GrnHill", "Landmark": "Landmrk",
}
NEIGHBORHOOD_NAMES = {code: long.replace("_", " ").replace("Iowa DOT and Rail Road", "Iowa DOT & Rail Road") for long, code in NEIGHBORHOOD_CODES.items()}
NEIGHBORHOOD_NAMES["SWISU"] = "South & West of ISU"

BLDG_TYPE = {"OneFam": "single_family", "TwnhsE": "townhouse", "Twnhs": "townhouse", "Duplex": "duplex", "TwoFmCon": "duplex"}

FEATURES = [
    "overallQual", "overallCond", "grLivArea", "totalBsmtSF", "garageCars", "garageArea",
    "yearBuilt", "yearRemodAdd", "fullBath", "bedroomAbvGr", "totRmsAbvGrd", "lotArea",
]


def read_arff(path: Path) -> pd.DataFrame:
    names: list[str] = []
    rows: list[list[str]] = []
    with open(path, encoding="utf-8") as f:
        in_data = False
        for line in f:
            line = line.rstrip("\n")
            if not in_data:
                low = line.lower()
                if low.startswith("@attribute"):
                    names.append(line.split()[1])
                elif low.startswith("@data"):
                    in_data = True
            elif line.strip() and not line.startswith("%"):
                rows.append(line.split(","))
    return pd.DataFrame(rows, columns=names)


def _int(v: str, default: int = 0) -> int:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default


def describe(p: Property) -> str:
    """Human-readable case text. This is what gets embedded and BM25-indexed, so it
    deliberately includes both the neighborhood code and its full name, numbers in
    plain form, and derived facts (age, remodel) that people phrase queries with."""
    name = NEIGHBORHOOD_NAMES.get(p.neighborhood, p.neighborhood)
    age = p.saleYear - p.yearBuilt
    remod = f", remodeled in {p.yearRemodAdd}" if p.yearRemodAdd > p.yearBuilt else ""
    kind = {"single_family": "single-family home", "townhouse": "townhouse", "duplex": "duplex"}.get(BLDG_TYPE.get(p.bldgType, "single_family"), "home")
    garage = f"a {p.garageCars}-car garage of {p.garageArea} sq ft" if p.garageCars else "no garage"
    bsmt = f"a {p.totalBsmtSF:,} sq ft basement" if p.totalBsmtSF else "no basement"
    era = "new construction" if age <= 2 else "recently built" if age <= 10 else "mid-age" if age <= 40 else "older" if age <= 70 else "historic"
    return (
        f"{p.bedroomAbvGr}-bedroom, {p.fullBath}-bath {kind} in {name} ({p.neighborhood}) with "
        f"{p.grLivArea:,} sq ft of living area above grade, {bsmt} and {garage}. "
        f"Built in {p.yearBuilt}{remod}; {age} years old at sale ({era}). "
        f"Overall quality {p.overallQual}/10, condition {p.overallCond}/10, {p.totRmsAbvGrd} rooms total, "
        f"on a {p.lotArea:,} sq ft lot. Sold in {p.saleYear} for ${p.salePrice:,}."
    )


@dataclass
class Dataset:
    properties: list[Property]
    frame: pd.DataFrame  # numeric feature frame aligned with `properties`
    by_id: dict[str, Property]
    neighborhood_stats: dict[str, dict]

    def __len__(self) -> int:
        return len(self.properties)


def load_dataset(path: Path) -> Dataset:
    raw = read_arff(path)
    props: list[Property] = []
    for i, r in enumerate(raw.itertuples(index=False)):
        d = r._asdict()
        p = Property(
            id=f"AMES-{i + 1:04d}",
            neighborhood=NEIGHBORHOOD_CODES.get(d["Neighborhood"], d["Neighborhood"]),
            salePrice=_int(d["Sale_Price"]),
            overallQual=QUAL_MAP.get(d["Overall_Qual"], 5),
            overallCond=QUAL_MAP.get(d["Overall_Cond"], 5),
            grLivArea=_int(d["Gr_Liv_Area"]),
            totalBsmtSF=_int(d["Total_Bsmt_SF"]),
            lotArea=_int(d["Lot_Area"]),
            garageCars=_int(d["Garage_Cars"]),
            garageArea=_int(d["Garage_Area"]),
            yearBuilt=_int(d["Year_Built"]),
            yearRemodAdd=_int(d["Year_Remod_Add"]),
            garageYrBlt=None,
            fullBath=_int(d["Full_Bath"]),
            bedroomAbvGr=_int(d["Bedroom_AbvGr"]),
            totRmsAbvGrd=_int(d["TotRms_AbvGrd"]),
            saleYear=_int(d["Year_Sold"]),
            bldgType=d["Bldg_Type"],
            summary="",
        )
        p.garageYrBlt = max(p.yearBuilt, p.yearRemodAdd - 2) if p.garageCars else None
        p.summary = describe(p)
        props.append(p)

    # Drop the handful of partial-sale outliers (GrLivArea > 4000 & cheap) — the
    # dataset author recommends this; they distort both comps and the model.
    props = [p for p in props if not (p.grLivArea > 4000 and p.salePrice < 300_000)]
    for i, p in enumerate(props):
        p.id = f"AMES-{i + 1:04d}"

    frame = pd.DataFrame([{k: getattr(p, k) for k in FEATURES} | {"neighborhood": p.neighborhood, "salePrice": p.salePrice, "saleYear": p.saleYear} for p in props])

    stats: dict[str, dict] = {}
    for nb, g in frame.groupby("neighborhood"):
        ppsf = g["salePrice"] / g["grLivArea"].clip(lower=1)
        stats[nb] = {
            "count": int(len(g)),
            "median": int(g["salePrice"].median()),
            "ppsf_median": float(ppsf.median()),
            "ppsf_cv": float(ppsf.std() / ppsf.mean()) if len(g) > 1 else 0.0,
            "median_year": int(g["yearBuilt"].median()),
            "median_qual": float(g["overallQual"].median()),
        }
    return Dataset(properties=props, frame=frame, by_id={p.id: p for p in props}, neighborhood_stats=stats)


def apply_filters(props: list[Property], f) -> list[Property]:
    out = []
    for p in props:
        if f.neighborhoods and p.neighborhood not in f.neighborhoods:
            continue
        if f.minYearBuilt and p.yearBuilt < f.minYearBuilt:
            continue
        if f.maxYearBuilt and p.yearBuilt > f.maxYearBuilt:
            continue
        if f.minBedrooms is not None and p.bedroomAbvGr < f.minBedrooms:
            continue
        if f.maxBedrooms is not None and p.bedroomAbvGr > f.maxBedrooms:
            continue
        if f.minGrLivArea and p.grLivArea < f.minGrLivArea:
            continue
        if f.maxGrLivArea and p.grLivArea > f.maxGrLivArea:
            continue
        if f.minQual and p.overallQual < f.minQual:
            continue
        if f.maxPrice and p.salePrice > f.maxPrice:
            continue
        out.append(p)
    return out


def city_median(ds: Dataset) -> int:
    return int(np.median([p.salePrice for p in ds.properties]))
