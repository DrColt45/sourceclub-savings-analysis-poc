# SourceClub Savings Analysis POC

This is a Streamlit prototype for SourceClub Assignment 1: Savings Analysis Automation.

The app lets a user upload a supplier purchase-analysis CSV/XLSX, maps the input columns into a standard SourceClub schema, compares the rows against a built-in demo SourceClub catalog, flags uncertain matches for review, and exports a sales-ready Excel workbook.

## Demo Modes

Demo Mode is designed to show the intended workflow end to end. The app includes three synthetic purchase-history options:

- `Built-in Generic Demo`
- `Benco Family Dentistry Demo`
- `Henry Schein Smile Center Demo`

For the clearest assignment demonstration, choose `Benco Family Dentistry Demo` or `Henry Schein Smile Center Demo`, keep the built-in SourceClub demo catalog enabled, then click **Run Savings Analysis**.

The app also includes download buttons for the Benco demo purchase history, Henry Schein demo purchase history, and demo SourceClub catalog. These files are useful for showing the upload workflow without using any real customer or supplier data.

Uploaded real-world files may show low savings or many no-match rows if their items do not overlap with the synthetic demo catalog. In that case, the app shows a catalog coverage warning so the result reads as limited demo coverage rather than a system failure. This is intentional: the prototype is conservative and should not invent savings when the catalog does not contain comparable products.

## What The App Does

- Uploads supplier purchase-history files.
- Provides demo-mode selection for generic, Benco-style, and Henry-Schein-style purchase histories.
- Uses `data/sourceclub_catalog_sample.csv` as the built-in synthetic demo catalog.
- Optionally accepts a replacement catalog upload for testing.
- Auto-detects purchase-history columns and lets the user edit the mapping.
- Runs deterministic and fuzzy product matching.
- Separates confirmed savings from potential/review savings.
- Flags no-match, higher-price, substitute, alternative, and UOM-review rows.
- Generates human/AI review prompts that can be pasted into ChatGPT or Claude.
- Exports `SourceClub_Savings_Analysis_Output.xlsx`.

## Four-Step Workflow

1. Select or upload a supplier purchase history.
2. Match rows against the built-in demo SourceClub catalog or an uploaded replacement catalog.
3. Review exceptions such as alternatives, substitutes, UOM issues, higher-price rows, and no-match rows.
4. Export a savings-ready workbook with summary, analysis, review queue, no-match/higher-price rows, and match-library candidates.

## Run Locally

On Windows, double-click:

```text
run_windows.bat
```

Or run manually from the project folder:

```powershell
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Then open the local Streamlit URL shown in the terminal, usually `http://localhost:8501`.

## Deploy On Streamlit Community Cloud

This repo is ready for Streamlit Community Cloud with `app.py` as the main file path.

High-level deployment steps:

1. Push this folder to a GitHub repository.
2. Go to [Streamlit Community Cloud](https://share.streamlit.io/).
3. Sign in with GitHub.
4. Create a new app.
5. Select the GitHub repo and branch.
6. Set the main file path to `app.py`.
7. Deploy.

See `DEPLOYMENT.md` for the full step-by-step guide.

## Files Included

- `app.py` - Streamlit entry point and user interface.
- `requirements.txt` - Python dependencies for local and cloud deployment.
- `run_windows.bat` - Windows launcher for local demo use.
- `.streamlit/config.toml` - basic deployed app configuration and theme.
- `core/normalization.py` - column detection, schema normalization, duplicate aggregation.
- `core/matching.py` - deterministic/fuzzy matching, savings classification, review prompts.
- `core/reporting.py` - summary metrics and Excel workbook export.
- `data/sourceclub_catalog_sample.csv` - synthetic demo catalog.
- `data/sample_purchase_history.csv` - synthetic demo purchase history.
- `data/demo_uploads/Benco_Family_Dentistry_Purchase_Analysis.csv` - synthetic Benco-style demo upload.
- `data/demo_uploads/HenrySchein_Smile_Center_Items_Purchased.csv` - synthetic Henry-Schein-style demo upload.
- `data/demo_uploads/*.xlsx` - Excel versions of the synthetic demo uploads.
- `scripts/smoke_test.py` - smoke test that imports the core logic and generates a sample workbook locally.
- `scripts/demo_upload_test.py` - demo coverage test for all included demo files plus a non-overlap guardrail.
- `reports/QA_RESULTS.md` - QA commands and demo metrics.
- `reports/DEMO_RESULTS_SUMMARY.md` - scenario-by-scenario demo results table.
- `DEPLOYMENT.md` - deployment checklist for GitHub and Streamlit Community Cloud.

## Sample Data Statement

All included CSV data is synthetic demo data. It does not contain real dental-office records, patient information, PHI, real customer files, credentials, private SourceClub data, or proprietary supplier catalog exports.

## Assumptions And Limitations

- The prototype works offline and does not require external AI APIs.
- `rapidfuzz` is used for fuzzy matching when installed. The app has a standard-library similarity fallback.
- Matching is intentionally conservative: uncertain substitutes, alternatives, and UOM issues are treated as review savings, not confirmed savings.
- Higher-price rows and no-match rows are excluded from confirmed savings.
- Pack-size normalization is a prototype heuristic and should be expanded with real supplier UOM rules before production use.
- Uploaded files are processed in the Streamlit session only; this prototype does not persist uploaded data or reviewer decisions.
- Uploaded purchase histories can produce low savings if they do not overlap with the demo catalog.
- The built-in catalog is a synthetic sample and is not a production SourceClub pricing catalog.
- In production, SourceClub would connect this app to its real secured pricing catalog and a confirmed match library.

## Recommended Next Work

- Add supplier-specific import profiles for Benco, Henry Schein, Patterson, Darby, Safco, Net32, and others.
- Add a durable match library so confirmed matches can be reused.
- Expand pack/UOM parsing and supplier SKU cross-reference tables.
- Add reviewer approval workflow and match training.
- Connect to a secured, versioned SourceClub catalog source.
- Add AI-assisted manufacturer SKU lookup and product reasoning for ambiguous matches, with reviewer approval before savings are confirmed.
