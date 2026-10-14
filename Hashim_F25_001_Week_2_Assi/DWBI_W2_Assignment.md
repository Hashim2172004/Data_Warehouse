# PakFreight — Week 2 assignment

Python notebook edition. The source evidence is retained unchanged in `data/`. Tasks 1–5 are answered here and in the notebook. The original activity workbook has separate classroom task numbering (T1–T7); those tabs are completed too. Student name and roll number can be entered before submission.

**Submission limitation:** The Python pipeline is executed and validated. Power Query M and DAX are supplied for Power BI, but no Power BI session was available: a genuine PBIX and Applied Steps/report screenshots are still required by the original rubric. Python plots are labelled as Python evidence and are not Power BI screenshots.

## Task 1 — Tiers and warehouse properties

| Tier | Job | PakFreight example | Must not happen |
|---|---|---|---|
| Staging | Preserve evidence and apply repeatable quality transformations | Parse marine dates with UK locale; convert rail tonnes to kg; reject road junk | Business users must not aggregate unclean source queries |
| Storage | Hold consistent integrated records and history | Store one row per shipment with common IDs, units and source identity | Overwrite historical dimension values without preserving versions |
| Presentation | Expose agreed measures and dimensional views | Show total weight and breakdown by transport mode | Apply a second rail unit conversion in a visual |

| Inmon property | Satisfied in PakFreight | Broken example |
|---|---|---|
| Subject-oriented | Organise all modes around the shipment business subject | Separate file-shaped reports with no shared shipment definition |
| Integrated | Same eight columns, kg unit, ID prefixes and canonical statuses | Interpret 32.5 rail tonnes as 32.5 kg |
| Time-variant | Retain dated shipments and effective-dated customer/route history | Replace old addresses so historical routes appear to use today's address |
| Non-volatile | Retain loaded facts; record corrections with an audit trail | Delete or overwrite yesterday's freight facts to hide an error |

| Requirement | Choice and reason |
|---|---|
| Truck positions every two minutes | ODS: current operational state with frequent updates |
| CFO cost per tonne-km over three years | EDW: consistent historical comparison; distance is additional required data |
| Did 45017 leave today? | ODS: current dispatch event/status; this February sample cannot answer today's question |
| Mode profitability since 2023 | EDW: historical costs and revenues; billing revenue is not in these files |

The notebook draws an independent arrangement in which each department loads its own file directly into its mart, and a dependent arrangement in which all sources pass through staging and one integrated warehouse before departmental marts. Independent marts apply local rules to inconsistent units and row definitions. Operations counts an aggregate row, Finance misreads the rail unit, and Sales counts a trip twice. A shared warehouse and conformed definitions make all three use the same accepted facts.

Raw files pass through staging so quality, schema and unit problems are detected and recorded before they affect shared measures.

**Address question:** Losing an old customer address principally breaks time variance and also conflicts with non-volatility if existing history is destructively changed. A type-2 slowly changing Customer dimension should retain the old version, add the new version with effective dates and a surrogate key, and keep historical facts linked to the appropriate version.

## Task 2 — Architecture and lifecycle

| Dimension | Inmon | Kimball |
|---|---|---|
| Starting point | Enterprise requirements and integrated core | Prioritised business process and enterprise bus plan |
| Core modelling | Normalised enterprise warehouse, usually 3NF | Dimensional facts and dimensions |
| First value | Usually slower due to broad integration | Earlier through one useful process mart |
| Main risk | Long initial delivery and expensive enterprise modelling | Inconsistent marts if conformance is ignored |
| Consistency | Enterprise model feeding dependent marts | Conformed dimensions and shared fact definitions |
| Delivery | Core warehouse followed by derived marts | Incremental process stars tied through the bus |

Original diagrams in the notebook show CIF (sources, staging, normalised EDW, dependent marts, reports) and Bus (sources, staging, process facts and shared dimensions). Neither architecture makes staging optional.

| Scenario | Choice | Reason |
|---|---|---|
| 1 Bank agrees enterprise customer first | Inmon | Enterprise definition precedes reporting |
| 2 Startup dashboard within six weeks | Kimball | A small process star delivers early |
| 3 Hospital, five systems, regulatory programme | Inmon | Integrated enterprise history supports regulatory consistency |
| 4 Shipments first, conformed Date and Route | Kimball | Process-first incremental delivery with conformance |
| 5 Normalised core feeding departmental marts | Inmon | Dependent marts derive from the EDW |
| 6 Telecom bronze/silver/gold lakehouse | Hybrid | Integrated layers support dimensional serving; layering alone is not decisive |
| 7 Census model agreed before loading | Inmon | Enterprise model is defined up front |
| 8 Returns reuses Product | Kimball | New process reuses a conformed dimension |
| 9 Six irreconcilable marts | Hybrid | Retain useful stars while integrating definitions/core; disconnected marts alone are not Kimball |
| 10 Bank integrates acquired competitor | Inmon | Enterprise customer/account integration is the stated priority; dimensional consumption may follow |

### Kimball lifecycle: Shipments iteration

1. Programme planning: scope iteration 1 to February shipments, name owners and agree 34 accepted records and weight reconciliation as acceptance criteria.
2. Business requirements: define shipment grain as one unique mode-prefixed shipment; agree canonical status and kg as the common unit.
3. Technical architecture: immutable file sources feed staging transformations, integrated storage and a presentation model.
4. Product selection: choose Power BI Desktop for required delivery and Python/Jupyter for reproducible profiling and independent checks.
5. Dimensional modelling: plan FactShipment and shared Date/Route dimensions; SourceSystem identifies mode. This week's eight-column table precedes the full star.
6. Physical design: select typed columns and stable shipment keys; plan surrogate keys and indexes in a database implementation.
7. ETL development: parse dates, multiply rail weights by 1,000, canonicalise text, quarantine road removals and append.
8. BI development: create weight and shipment-count measures, mode bar chart and status counts.
9. Deployment: validate row counts, totals, date traps and staging load settings before publishing.
10. Maintenance: monitor refresh failures, unit contracts, duplicate exceptions and export schema changes.

Iteration 2 Billing should reuse **Date and Route**. Conformed means their keys, attribute meanings and hierarchies are agreed and shared across shipment and billing stars; different event dates use the same Date dimension in different roles. Customer is another useful conformed dimension, but its keys need a new authoritative source because these files do not provide customer identity.

SDLC begins with requirements and builds a program to meet them. CLDS begins by examining available data, then refines realistic requirements through profiling and feedback. For example, the rail header reveals the tonne unit, and the road file reveals that physical lines are not shipment counts. This is an iterative discovery emphasis, not a rule that Kimball ignores requirements or Inmon never examines data.

**Architecture question:** Shipments first with conformed dimensions is bottom-up Kimball. For a top-down interpretation, an enterprise integrated normalised core would already have been designed and built, and the Shipments mart would be derived from it.

## Task 3 — Data Detective and reconciliation

The completed activity workbook records 12 issues with examples and impacts. Marine has text dates, uppercase statuses and hidden spaces. Rail has two title rows, a tonnes unit, numeric identifiers and mixed-case/space-padded statuses. Road has lowercase IDs, ISO text dates, a duplicate, an empty record and a non-data TOTAL record with missing mandatory fields. No real shipment has a missing mandatory date, ID or weight; the missing values belong to junk rows. Different location types are retained as supplied: Karachi Port and Karachi Cantt must not be merged merely because both are in Karachi.

### Exact stovepipe arithmetic

| Department | Arithmetic in kg | Tonnes | Error |
|---|---|---|---|
| Operations | 206,500 + 295,250 + (166,000 − 6,100) = 661,650 | 661.65 | Removes the duplicate but keeps road TOTAL = 83,000 kg |
| Finance | 206,500 + 295.25 + 76,900 = 283,695.25 | 283.69525 → 283.70 | Rail tonnes treated as kg; display rounded to two decimals |
| Sales | 206,500 + 295,250 + 83,000 = 584,750 | 584.75 | Keeps the second 6,100 kg trip after removing TOTAL |
| Shared staging | 206,500 + 295,250 + 76,900 = 578,650 | 578.65 | Correct grain, units and filtering |

Each department used internally consistent rules and obtained a plausible sum from its local file. They believed the totals because they had no shared unit, shipment-grain definition or cross-source reconciliation.

| Source | Raw records | Removed | Loaded | Weight kg |
|---|---:|---:|---:|---:|
| Marine | 12 | 0 | 12 | 206,500 |
| Rail | 10 | 0 | 10 | 295,250 |
| Road | 15 | 3 | 12 | 76,900 |
| Total | 37 | 3 | 34 | 578,650 |

### Named exclusions and lineage

1. `marine_shipments.csv`: header on physical line 1; data lines 2–13. Rename columns, parse every date as dd/mm/yyyy, trim/proper-case status, retain kg and add Marine. Keep all 12 records.
2. `rail_shipments.xlsx`, sheet Rail: remove title rows 1–2, promote row 3, load worksheet rows 4–13. Rename columns, parse native Excel dates, prefix IDs with RL-, multiply each of 10 tonne values by 1,000, trim/proper-case status and add Rail.
3. `road_shipments.csv`: header line 1; records lines 2–16. Uppercase IDs; remove physical line **15**, the all-empty record; remove line **16**, `TOTAL` (83,000 kg), because it summarises rows and has no shipment date; remove line **7**, the repeated `rd-505` (6,100 kg), retaining its identical first occurrence at line **6**. Parse remaining ISO dates, trim/proper-case status and add Road. Workbook staging equivalents are rows 18, 19 and 10 respectively; original Road_Raw equivalents are rows 15, 16 and 7.
4. Append by common column names into 34 × 8 `Shipments`; preserve source-file and raw-row provenance separately in `results/lineage.csv` so the required eight-column schema stays exact.
5. Sum kg at accepted shipment grain: 206,500 + 295,250 + 76,900 = 578,650. Divide that measure by 1,000 for the displayed 578.65 tonnes. Validate all rows are in February 2026.

The workbook uses formulas for dates, units, IDs, status, Keep flags and rejection reasons; original raw sheets stay intact. Reconciliation checks independently compare derived results to supplied controls.

| Process | Date | Customer | Route | Vehicle | Driver | Station/Port | Commodity |
|---|---|---|---|---|---|---|---|
| Shipments | X | X | X | X | X | X | X |
| Billing & Invoicing | X | X | X |  |  | X | X |
| Fleet Maintenance | X |  |  | X |  | X |  |
| Fuel Purchases | X |  | X | X | X | X |  |
| Driver Trips & Hours | X |  | X | X | X | X |  |
| Customer Complaints | X | X | X |  |  |  | X |

This is a proposed enterprise bus, not a claim that all dimension attributes already exist in the three files. Vehicle, Driver, Customer and Commodity need additional source data. Date appears in every process. Date, Route and Customer should be agreed across Finance, Operations and Sales, along with the shipment-grain/unit rules. Plan the whole bus while delivering one process at a time; build Shipments first for the COO.

**TOTAL control:** Filter/quarantine identifiers equal to TOTAL before modelling, require mandatory shipment keys and dates, and fail validation if aggregate rows survive. Preserve an exclusion log so the control remains auditable.

## Task 4 — Reproducible pipeline and Power BI handoff

The notebook implements staging, integrated eight-column storage and Python presentation. It retains raw DataFrames separately and exports only accepted Shipments for analysis. It checks 34 rows, eight exact columns, no missing ID/date/weight, unique IDs, three canonical statuses, February dates and both locale traps. Results are Delivered 22, In Transit 8, Delayed 4; Marine 206.5 t, Rail 295.25 t, Road 76.9 t.

In Power BI use **Transform Data** because schema, date locale and row-quality rules must be recorded before anything loads into the model. Rail automatic header promotion is wrong because worksheet row 1 is a title, not the seven-column header; remove two title rows before promoting row 3. Append aligns names rather than positions.

The supplied `power_query/` files define `DataFolder`, `marine_stg`, `rail_stg`, `road_stg` and `Shipments`. Paste each into a blank query's Advanced Editor. See `POWER_BI_SETUP.md` for query creation order and validation visuals. Disable Enable load on all three staging queries, leaving only Shipments loaded. This keeps the quality tier separate from integrated storage/presentation and prevents users from selecting raw/staged tables, double-counting appended records or mixing units. In this introductory implementation a loaded Power BI table represents integrated storage; a production EDW would persist data independently.

### Rail M annotations

The complete authored rail M is in `power_query/rail_stg.pq` and is displayed in the notebook. It was authored from the observed input, not copied from a live Advanced Editor session.

- `Table.Skip(Raw, 2)` removes the title and unit-description rows so the true header can be promoted.
- `Table.AddColumn(Typed, "WeightKG", each [#"Weight (Tons)"] * 1000, type number)` converts each rail weight once at staging.
- `Table.TransformColumns(... Text.From ... "RL-" ...)` creates a stable text ID with the rail namespace so keys from different modes cannot collide.

**Folder bonus:** Combine & Transform creates a sample-file query and a reusable transformation function, then invokes it for each selected file in the folder and appends results. Filter file extensions and exclude hidden/temporary files before combining, retain file identity, and apply row/schema controls per file. One malformed export can fail the function or pollute the combined results, so a folder connector needs the same contracts and quarantine discipline as an individual file connector.

## Task 5 — Latency, drift, lineage and ownership

| Consumer | Freshness | Reason |
|---|---|---|
| Dispatcher avoiding blocked motorway | Near-real-time, event updates within seconds to two minutes | Routing decisions need current positions and incident events |
| CFO monthly cost-per-tonne | Daily batch | Latest reconciled daily totals are sufficient for monthly analysis |
| Online consignment tracking | Near-real-time, about two minutes | Customers need recent accepted dispatch/delivery events |
| Quarterly board review | Weekly, then final period-close snapshot | Decisions depend on reconciled trends rather than second-by-second movement |

Always real-time adds streaming/compute/monitoring cost and increases operational coupling: partial, late or conflicting events require ordering and deduplication logic. A frequently changing unclosed total also increases reconciliation work without improving a quarterly decision.

### Schema drift in the supplied M

| Rail change | Exact next-refresh behaviour | Detection/control |
|---|---|---|
| Adds Wagon_Type | Continues; final explicit eight-column selection drops the unused extra field | Compare actual header set to an approved schema and flag additions before they silently disappear |
| Renames Freight Charges (PKR) to Charges_PKR | Fails at RenameColumns with missing required old column; no MissingField.Ignore is used | Required-column contract test on promoted headers, alert owner and approve a versioned mapping |

This behaviour depends on the actual authored code. A pipeline that appends every field without an explicit projection would instead introduce Wagon_Type into the model and violate the eight-column contract. Source owners must communicate planned changes before refreshing a production model.

### Metric lineage and investigation

Three unchanged sources → source-specific staging (marine locale, rail ×1,000, road blank/TOTAL/duplicate exclusions) → append eight common columns → accepted Shipments → SUM(WeightKG) card = 578,650 → tonne display = 578.65.

If the CFO thinks the number is too low, first verify source completeness, reporting period and rail units against raw exports. Second inspect staged conversion and the exact three rejection records, checking whether a legitimate shipment was rejected. Third check append coverage, report date/status filters and measure definition; do not change a control value to fit a preferred answer.

| Responsibility | Owner | Main tier |
|---|---|---|
| Shipment star schema | Data architect | Storage and presentation boundary |
| Power Query maintenance | ETL/data engineer | Staging |
| Official Delivered definition | Business/data steward | Cross-tier semantic governance |
| Morning operations dashboard | BI developer | Presentation |
| Rail export contract | Source system owner | Source interface into staging |

The data engineer owns staging and its rejection/quality logs; without that owner the rail unit and road junk reach reports. The architect owns integrated storage and shared grain/keys; without that owner three inconsistent marts persist. The BI developer owns presentation with steward-approved measures; without that ownership report-specific filters or hidden conversions recreate the stovepipe totals. Stewardship is needed across all three tiers for business definitions.

A freight analyst must validate their own output because a precise-looking number can still have the wrong unit or grain. If Finance's 283,695.25 kg were accepted, PakFreight would understate volume by 294,954.75 kg; cost-per-tonne would be inflated and could lead to a wrong rail pricing or capacity decision. Recorded controls protect decisions and make later correction possible.

**Inherited dashboard:** Record its measure, filters, time period and last successful refresh before changing it. Follow lineage back through the model and append to immutable exports, independently recompute the figure and compare accepted/rejected rows. Check whether source event time and refresh latency explain the mismatch, then compare actual schemas/units to the contracts and review failed or skipped transformations. Resolve the cause with the relevant owner, rerun controls and document the corrected lineage before republishing.
