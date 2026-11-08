# Week 7 — PakFreight Integration Lab
Hashim Nadeem | SU92-BDSFM-F25-001 | BS DS-7a

The uploaded assignment is Week 7; this was confirmed before completion.

## Open and run
1. Extract the entire ZIP.
2. Install dependencies with `pip install -r requirements.txt`.
3. Start Jupyter from this folder and open `W7_SU92-BDSFM-F25-001_Hashim_Nadeem.ipynb`.
4. Run all cells. The notebook already contains executed outputs.

The notebook contains all T1–T8 written answers, the complete named pandas pipeline, result tables, twelve asserted checks, temporal and foreign-key checks, historical preservation checks, and a second-run idempotence check. Original input files are under data/. The uploaded student workbook is an unchanged reference; completed answers are in the requested notebook format.

results/ contains the five required load tables, updated dimensions, rejects, duplicate and structural-removal logs, profiling, OLAP summaries, unresolved values and validation evidence. `pipeline.py` provides the same reusable extraction/transformation functions separately. `Reflection_Hashim_Nadeem.md` contains the reflection.

The nine code cells were executed sequentially in Python with rich outputs captured. A separate networked Jupyter kernel could not start in the execution environment; validation ran successfully in-process. This does not affect opening or running the notebook in Jupyter locally.

Expected result: 12/12 checks PASS; 1,700 April shipments, 17,915,700 kg, PKR 158,037,000. Integrated: 2,934 shipments, 36,036,400 kg, PKR 309,882,000. March's customer-HQ Punjab total remains 7,566,850 kg.
