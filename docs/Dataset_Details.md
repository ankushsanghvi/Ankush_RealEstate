# Valora — Dataset Details

## Summary

| Item | Value |
|---|---|
| Dataset name | **Ames Housing Dataset** (Dean De Cock, *Journal of Statistics Education*, 2011) |
| Dataset source | OpenML, dataset id **43926** (the primary dataset named in the project brief) |
| Dataset link | <https://www.openml.org/search?type=data&sort=runs&id=43926> |
| Data format | ARFF (attribute-relation file format: a CSV body with a typed header), 2.1 MB |
| Location in repo | `backend/data/ames_housing.arff` (full dataset) · `data/sample_data/ames_housing_sample.csv` (100-row processed extract) |
| Size | 2,930 residential property sales × 81 columns |
| Period | Sales from 2006 to 2010, Ames, Iowa (USA) |
| Records used | 2,927 (3 partial-sale outliers removed, see *Preprocessing*) |
| Licence | Public; published for educational use by the author |

## Dataset purpose

Each row is one historical sale with the property's characteristics and its sale price. That supports
everything the assistant needs to do:

- **Similar-property retrieval (RAG):** every sale becomes a searchable "property case".
- **Comparable-property identification and prioritization:** appraisers value a home from recent nearby sales of similar homes.
- **Price prediction:** a supervised regression target (`Sale_Price`) with 80 explanatory columns.
- **Feature and location impact analysis:** 28 neighborhoods and rich physical attributes support a hedonic model of what drives price.
- **Risk analysis:** neighborhood price dispersion and coverage indicate how reliable a valuation is.
- **Honest evaluation:** real sale prices let us measure valuation error on held-out records.

## Key fields

The project brief lists 15 key fields. Their OpenML column names and their use in Valora:

| Brief field | OpenML column | Type | Range in data (min · median · max) | Used for |
|---|---|---|---|---|
| SalePrice | `Sale_Price` | integer, USD | 12,789 · 160,000 · 755,000 | target; comparables; evaluation ground truth |
| OverallQual | `Overall_Qual` | ordinal text → 1–10 | 1 · 6 · 10 | filter `minQual`; comparable priority; model; adjustments |
| OverallCond | `Overall_Cond` | ordinal text → 1–10 | 1 · 5 · 9 | model; compare factors |
| GrLivArea | `Gr_Liv_Area` | integer, sq ft | 334 · 1,442 · 4,476 | filter; comparable priority (±10 %); $/sq ft; model |
| TotalBsmtSF | `Total_Bsmt_SF` | integer, sq ft | 0 · 990 · 3,206 | model; adjustments |
| GarageCars | `Garage_Cars` | integer | 0 · 2 · 5 | model; adjustments |
| GarageArea | `Garage_Area` | integer, sq ft | — | model; case text |
| YearBuilt | `Year_Built` | integer | 1872 · 1973 · 2010 | filter; comparable priority (±8 years); model |
| YearRemodAdd | `Year_Remod_Add` | integer | — | model; case text ("remodeled in …") |
| FullBath | `Full_Bath` | integer | — | model; case text |
| BedroomAbvGr | `Bedroom_AbvGr` | integer | 0 · 3 · 8 | filter; comparable priority |
| TotRmsAbvGrd | `TotRms_AbvGrd` | integer | — | model; case text |
| Neighborhood | `Neighborhood` | categorical, 28 values | — | filter; comparable priority; hedonic fixed effects; risk |
| LotArea | `Lot_Area` | integer, sq ft | 1,300 · 9,430 · 215,245 | model; case text |
| GarageYrBlt | *not present in OpenML 43926* | — | — | **derived**, see below |

Supporting columns we also use: `Year_Sold` (recency of a comparable; age at sale) and `Bldg_Type`
(single-family 2,422 · townhouse 334 · duplex / two-family 171) for property-type classification.

**GarageYrBlt.** The OpenML version of the dataset drops this column. Valora derives it as
`max(YearBuilt, YearRemodAdd − 2)` for homes that have a garage, and `null` otherwise. It is shown for
information only and is not used by the model or by comparable scoring, so the approximation cannot
bias a valuation.

## Data preprocessing performed

All preprocessing is in `backend/app/data/loader.py` and runs at startup (about 1 s). Derived
artifacts are cached by a hash of the data.

1. **Parsing.** A small, dependency-free ARFF reader turns the typed header and CSV body into a DataFrame.
2. **Type coercion.** Numeric columns are cast to integers. Malformed values fall back to 0 (the OpenML
   release has no missing values in the fields we use).
3. **Ordinal mapping.** Quality and condition labels (`Very_Poor` … `Very_Excellent`) are mapped to the 1–10 scale
   used in the original Ames documentation and by appraisers.
4. **Code normalisation.** OpenML's long neighborhood labels (`North_Ames`, `College_Creek`, …) are mapped
   to the canonical Ames codes (`NAmes`, `CollgCr`, …). The full names are kept for display and search.
5. **Outlier removal.** Three partial sales with more than 4,000 sq ft selling below $300,000 are dropped,
   as the dataset author recommends. They are not representative arm's-length sales and would distort
   both comparables and the regressor. Result: 2,927 records with stable ids `AMES-0001 … AMES-2927`.
6. **Chunking: the "property case".** Each record becomes exactly one chunk, a natural-language summary
   that is embedded and BM25-indexed. One record = one chunk because a sale is an atomic unit of evidence:
   splitting it would separate a price from the attributes that explain it. Example:

   > 3-bedroom, 1-bath single-family home in North Ames (NAmes) with 1,656 sq ft of living area above
   > grade, a 1,080 sq ft basement and a 2-car garage of 528 sq ft. Built in 1960; 50 years old at sale
   > (older). Overall quality 6/10, condition 5/10, 7 rooms total, on a 31,770 sq ft lot. Sold in 2010
   > for $215,000.

   The text deliberately includes both the neighborhood code and its full name, numbers in plain form, and
   derived facts (age at sale, an era word, remodel year), because those are the words people use in queries.
7. **Numeric feature frame.** The 12 model features plus neighborhood, price and sale year, aligned
   row-for-row with the property cases.
8. **Neighborhood statistics.** For each neighborhood: sale count, median price, median $/sq ft, $/sq ft
   coefficient of variation (volatility), median year built and median quality. These drive the valuation
   narrative, comparable fallbacks and the risk score.
9. **Model features.** The pricing model trains on `log(Sale_Price)` with the 12 numeric features plus
   neighborhood median $/sq ft and median price as location encodings (`backend/app/agents/pricing.py`).

## Distribution notes

- **Neighborhood coverage is uneven:** North Ames 443 sales, College Creek 267, Old Town 239 … Green Hills 2,
  Landmark 1. Valuations in thin neighborhoods fall back to similar homes elsewhere, and the risk score
  rises accordingly ("Neighborhood coverage" driver).
- **Prices are right-skewed** (mean $180,801 vs median $160,000). That is why the model uses a log target and
  why errors are reported as percentages (MAPE).
- **The sales span 2006–2010**, including the 2008 downturn. Comparables get a small priority bonus for
  recent sales; full time-adjustment is listed as future work.

## Sample data

`data/sample_data/ames_housing_sample.csv` holds 100 processed records (every 29th record), with all typed
fields and the generated `summary` text. It shows the exact shape the retrieval layer indexes. To
regenerate the full processed set, start the backend; it is built from the ARFF in about one second.
