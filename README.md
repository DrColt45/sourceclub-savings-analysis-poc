# SourceClub Savings Analysis POC

This is a Streamlit prototype for SourceClub Assignment 1: Savings Analysis Automation.

The app lets a user upload a supplier purchase-analysis CSV/XLSX, maps the input columns into a standard SourceClub schema, compares the rows against a built-in demo SourceClub catalog, flags uncertain matches for review, and exports a sales-ready Excel workbook.

## What The App Does

- Uploads supplier purchase-history files.
- Uses `data/sourceclub_catalog_sample.csv` as the built-in demo catalog.
- Optionally accepts a replacement catalog upload for testing.
- Auto-detects purchase-history columns and lets the user edit the mapping.
- Runs deterministic and fuzzy product matching.
- Separates confirmed savings from potential/review savings.
- Flags no-match, higher-price, substitute, alternative, and UOM-review rows.
- Generates human/AI review prompts that can be pasted into ChatGPT or Claude.
- Exports `SourceClub_Savings_Analysis_Output.xlsx`.

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
- `scripts/smoke_test.py` - smoke test that imports the core logic and generates a sample workbook locally.
- `DEPLOYMENT.md` - deployment checklist for GitHub and Streamlit Community Cloud.

## Sample Data Statement

All included CSV data is synthetic demo data. It does not contain real dental-office records, patient information, PHI, real customer files, credentials, private SourceClub data, or proprietary supplier catalog exports.

## Assumptions And Limitations

- The prototype works offline and does not require external AI APIs.
- `rapidfuzz` is used for fuzzy matching when installed. The app has a standard-library similarity fallback.
- Matching is intentionally conservative: uncertain substitutes, alternatives, and UOM issues are treated as review savings, not confirmed savings.
- Pack-size normalization is a prototype heuristic and should be expanded with real supplier UOM rules before production use.
- Uploaded files are processed in the Streamlit session only; this prototype does not persist uploaded data or reviewer decisions.
- The built-in catalog is a small synthetic sample and is not a production SourceClub pricing catalog.

## Recommended Next Work

- Add supplier-specific import profiles for Benco, Henry Schein, Patterson, Darby, Safco, Net32, and others.
- Add a durable match library so confirmed matches can be reused.
- Expand pack/UOM parsing and supplier SKU cross-reference tables.
- Add reviewer approval workflow and match training.
- Connect to a secured, versioned SourceClub catalog source.
