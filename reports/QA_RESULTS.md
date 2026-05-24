# QA Results

## Status

PASS

## Commands Run

```powershell
python -m compileall .
python scripts\smoke_test.py
python scripts\demo_upload_test.py
```

Local Streamlit HTTP verification is also part of the final validation pass:

```powershell
python -m streamlit run app.py
```

## Demo Metrics

| Demo scenario | Rows analyzed | Coverage % | Confirmed savings | Review savings | Auto-confirmed | Review rows | No match/higher price |
|---|---:|---:|---:|---:|---:|---:|---:|
| Built-in Generic Demo | 12 | 91.7% | $318.00 | $46.00 | 7 | 2 | 3 |
| Benco Family Dentistry Demo | 14 | 92.9% | $282.20 | $238.50 | 5 | 7 | 2 |
| Henry Schein Smile Center Demo | 14 | 92.9% | $499.60 | $39.00 | 10 | 2 | 2 |
| Non-overlap synthetic upload | 3 | 0.0% | $0.00 | $0.00 | 0 | 0 | 3 |

## Coverage Guardrail

The deliberately unrelated upload produced 0.0% catalog coverage and no confirmed or review savings. This confirms the low-coverage warning condition works and the prototype does not invent savings when the demo catalog does not contain comparable products.

## Known Limitations

- The catalog and purchase histories are synthetic and intentionally small compared with a production SourceClub catalog.
- Matching is deterministic/fuzzy and offline; there is no API-backed AI lookup.
- UOM and pack normalization is enough for the demo but should be expanded for real supplier-specific unit conventions.
- Review decisions are not persisted across sessions.
- The match library output is a workbook-ready placeholder, not a durable database.

## Data Safety

All included data is synthetic demo data. The repo does not include real dental office data, PHI, credentials, private SourceClub data, proprietary supplier catalogs, or real SourceClub pricing.
