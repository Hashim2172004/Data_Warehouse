# PakFreight Week 5 — Completed notebook submission

Open `PakFreight_W5_Completed.ipynb`. It contains T1–T7, the complete runnable pipeline, executed outputs, and the refresh evidence image.

## Run

1. Extract the ZIP fully.
2. Open a terminal in this folder.
3. Install dependencies: `pip install -r requirements.txt`.
4. Start Jupyter: `jupyter notebook PakFreight_W5_Completed.ipynb` and Run All.

For standalone ETL only: `python pipeline.py`.

## Contents

- Completed `.ipynb`: all written answers and executed calculations.
- `pipeline.py`: reusable ETL with named STEPS and retained intermediate frames.
- `original_files/`: all 16 supplied files, unchanged (including original student workbook).
- `data/`: canonical source filenames, night-two sources, five supplied dimensions, reference alias map.
- `outputs/night1/`, `outputs/night2/`: six-table CSV stars and SQLite databases, extraction logs, duplicate/unknown audits and checks.
- `outputs/refresh_before_after.png`: executed-result evidence image, also embedded in the notebook.
- `outputs/staging/`: byte-identical source copies for audit; not reporting tables.

Baseline: 8/8 checks; 34 rows, 578,650 kg, PKR 4,808,000; 0 Unknown city rows.
Refresh: 6/6 checks; 35 rows, 584,950 kg, PKR 4,860,000; 1 Unknown city row (Chaman Border).

Source discrepancy: night two changes trailing whitespace in status, not ShipmentID. Whole-row dedup before trimming reproduces the brief's 36-row failure; ID-only dedup before trimming still succeeds on these fixtures. The notebook demonstrates both and explains the distinction.

The requested notebook replaces the workbook answer format; the original workbook is preserved, not filled. No roll/team number was supplied. Rename the submission if your LMS requires one.
