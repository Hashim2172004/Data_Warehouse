# Week 6 reflection
Hashim Nadeem | SU92-BDSFM-F25-001 | BS DS-7a

I used pandas to build the March load and SQLite to demonstrate the date index. My data-row reconciliation is 1,284 extracted = 1,200 loaded + 24 rejected + 60 duplicate copies. The final fact contains 17,542,050 kg and PKR 147,037,000. All ten required checks pass.

I rejected nine text-weight exceptions, six invalid dates, five negative weights and four missing consignment IDs. Trimming cannot recover an unknown physical weight, an impossible date or a missing identity. My six-column RejectLog holds the batch, original file, physical row, complete raw source record, reason codes and UTC timestamp. A corrected source row can be submitted again. The scientific-notation token 1.2e4 is quarantined under the exercise's ordinary-decimal contract; interpreting it automatically would change the supplied controls.

I retained the three negative-cost credit notes. Together they reduce freight cost by PKR 283,000. A negative amount can be valid accounting history even when a negative physical weight is invalid.

Fourteen shipments use city -1: Keti Bandar Jetty (3), Kotri Junction (3), Wagah Border (2), Taftan Crossing (2), Torkham Gate (2) and Chaman Border (2). Seven use status -1: held at customs (4), RTO (2) and Hold (1). Their essential facts are valid, so an unresolved descriptor is a mapping task rather than a reason to delete a shipment. Deleting the fourteen city rows would hide 195,150 kg and leave 1,186 shipments. My UnknownLookupAudit keeps each affected source row visible.

I removed duplicates only after normalizing consignment IDs. Comparing raw rows leaves twelve trailing-space copies. Comparing day, lane, weight and customer goes too far: RD-5216 / RD-5337 and RD-5332 / RD-5409 are separate shipments with matching attributes. I also conformed 46 registry IDs into 40 businesses and retained all aliases. Changing customer keys changes grouping, not additive totals.

I would build a DateKey index because date ranges are used throughout the dashboard. Its 31 values have at most 40 rows each. ShipmentID is more selective but seldom queried; ModeKey has only three values and road covers 660 rows. One extra index requires 1,200 additional index-entry insertions for a full March load, plus storage and maintenance. SQLite EXPLAIN confirms an indexed SEARCH replaces the table SCAN. A star traverses one join instead of the requested snowflake's three.

Finally, I preserved the blank road record and TOTAL footer separately: the physical inputs contain 1,286 records, while the brief's 1,284 counts data rows. RawLanding and StructuralAudit reconcile this discrepancy without silent deletion. I rebuilt the stale 28-day date dimension into the 90 days of Q1.
