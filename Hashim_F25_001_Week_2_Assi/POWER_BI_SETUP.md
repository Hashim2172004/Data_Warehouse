# Complete the Power BI part in Desktop

These scripts have been authored from the source data. They have not been executed in Power BI here.

1. Extract all files. Open Power BI Desktop → Transform Data → New Source → Blank Query. Name the query `DataFolder`. Paste `power_query/DataFolder.pq` into Advanced Editor and replace the path with the full Windows path of your extracted `data` directory. M uses literal backslashes; use `"C:\PakFreight\data"`, without doubling them.
2. Create three blank queries named `marine_stg`, `rail_stg`, `road_stg`. Paste the matching `.pq` code. Inspect the named Applied Steps and compare the raw header/units. For a click-by-click version: import each source with Transform Data; rail Remove Top Rows = 2, then Promote Headers; rename to the common contract; apply UK date locale, rail ×1,000, IDs, text cleaning and road exclusions as in the scripts.
3. Create `Shipments` from its `.pq`. Untick Enable load on every `_stg` query and keep only Shipments loaded. A scalar DataFolder query is a parameter-like helper, not a model table.
4. In Power Query View enable Column quality, Column distribution and Column profile; switch profiling to the entire dataset. Confirm 34 rows and 8 columns; ID/date/weight have no Empty or Error; status has 3 distinct values. MR-1003 = 03-Feb-2026, MR-1012 = 13-Feb-2026, RL-45012 = 32,500 kg.
5. Close & Apply. Add each measure from `Measures.dax` separately. Use a card for Total Weight KG (display units None, zero decimals): 578,650. Use SourceSystem on a bar-chart axis and Total Weight Tonnes as value: Marine 206.5, Rail 295.25, Road 76.9. Use a status table with Shipment Count: Delivered 22, In Transit 8, Delayed 4.
6. Save as `DWBI_W2_<RollNo>.pbix`. Capture a genuine screenshot of rail or road Applied Steps and a genuine screenshot of the report card and validation visuals. Include them with the submission. Do not label supplied Python figures as Power BI screenshots.

## Controls and refresh

The fixed February lab controls stop refresh if shipment count/weight or key checks fail; revise them through an approved control table when moving to a new period. The M road distinct step is appropriate here because the two duplicate records are identical. For future conflicting duplicates, add a comparison/quarantine check instead of silently retaining the first.

A newly added rail Wagon_Type field is discarded by the final eight-column projection. Renaming Freight Charges (PKR) breaks its required rename step. For production, compare source headers to a versioned schema before transformations and retain file/row-level rejection logs outside the report table.
