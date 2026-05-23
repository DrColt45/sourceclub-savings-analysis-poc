# Deployment Guide

This guide publishes the SourceClub Savings Analysis POC to Streamlit Community Cloud from a GitHub repository.

The app is designed to deploy from the repository root with:

- Repository name: `sourceclub-savings-analysis-poc`
- Branch: `main`
- Main file path: `app.py`

## 1. Create A GitHub Repository

1. Sign in to GitHub.
2. Create a new repository named `sourceclub-savings-analysis-poc`.
3. Choose Public or Private based on SourceClub's sharing preference.
4. Do not add a README, `.gitignore`, or license in GitHub if those files already exist locally.

## 2. Push The Project

From the `sourceclub_savings_ui_app` folder:

```powershell
git init
git add .
git commit -m "Prepare SourceClub savings analysis POC"
git branch -M main
git remote add origin https://github.com/YOUR_GITHUB_USERNAME/sourceclub-savings-analysis-poc.git
git push -u origin main
```

If the remote already exists, update it instead:

```powershell
git remote set-url origin https://github.com/YOUR_GITHUB_USERNAME/sourceclub-savings-analysis-poc.git
git push -u origin main
```

## 3. Deploy On Streamlit Community Cloud

1. Go to [Streamlit Community Cloud](https://share.streamlit.io/).
2. Sign in with GitHub.
3. Select **Create app** or **New app**.
4. Choose the repository: `sourceclub-savings-analysis-poc`.
5. Choose the branch: `main`.
6. Set the main file path to: `app.py`.
7. Confirm advanced settings are empty unless SourceClub later adds secrets or environment variables.
8. Click **Deploy**.

Streamlit will install packages from `requirements.txt`, run `app.py`, and provide a public `.streamlit.app` URL.

## 4. Verify The Deployment

After deployment:

1. Open the public Streamlit URL.
2. Confirm the sample purchase history loads.
3. Click **Run Savings Analysis**.
4. Confirm the summary metrics and tabs appear.
5. Open the **Export** tab.
6. Download `SourceClub_Savings_Analysis_Output.xlsx`.

## 5. Safety Notes

- The included CSV files are synthetic demo data only.
- Do not upload real customer files, PHI, credentials, private SourceClub data, or proprietary supplier catalogs to a public GitHub repository.
- The prototype does not require AI APIs, API keys, secrets, passwords, or external services at runtime.
- If SourceClub later uses real catalog data, use a private repository or a secure hosted data source.
