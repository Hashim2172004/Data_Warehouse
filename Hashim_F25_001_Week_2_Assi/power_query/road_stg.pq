let
    Source = Csv.Document(File.Contents(DataFolder & "\road_shipments.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Renamed = Table.RenameColumns(Headers, {{"trip_id","ShipmentID"},{"trip_date","ShipDate"},{"from_city","Origin"},{"to_city","Destination"},{"weight_kg","WeightKG"},{"cost_pkr","CostPKR"},{"status","Status"}}),
    Indexed = Table.AddIndexColumn(Renamed, "RawRow", 2, 1, Int64.Type),
    UpperIDs = Table.TransformColumns(Indexed, {{"ShipmentID",each if _ = null then "" else Text.Upper(Text.Trim(_)),type text}}),
    RemovedBlankRows = Table.SelectRows(UpperIDs, each List.AnyTrue(List.Transform(Record.FieldValues(Record.RemoveFields(_, {"RawRow"})), each _ <> null and Text.Trim(Text.From(_)) <> ""))),
    RemovedTotal = Table.SelectRows(RemovedBlankRows, each [ShipmentID] <> "TOTAL"),
    // Buffer the sorted rows so the first identical RD-505 occurrence is retained.
    Buffered = Table.Buffer(Table.Sort(RemovedTotal, {{"RawRow",Order.Ascending}})),
    RemovedDuplicates = Table.Distinct(Buffered, {"ShipmentID"}),
    Typed = Table.TransformColumnTypes(RemovedDuplicates, {{"ShipmentID",type text},{"ShipDate",type date},{"Origin",type text},{"Destination",type text},{"WeightKG",type number},{"CostPKR",Currency.Type},{"Status",type text}}, "en-GB"),
    Cleaned = Table.TransformColumns(Typed, {{"Status",each Text.Proper(Text.Trim(_)),type text},{"Origin",Text.Trim,type text},{"Destination",Text.Trim,type text}}),
    Tagged = Table.AddColumn(Cleaned, "SourceSystem", each "Road", type text),
    Contract = Table.SelectColumns(Tagged, {"ShipmentID","ShipDate","Origin","Destination","WeightKG","CostPKR","Status","SourceSystem"})
in
    Contract
