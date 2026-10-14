let
    Source = Excel.Workbook(File.Contents(DataFolder & "\rail_shipments.xlsx"), null, true),
    Raw = Source{[Item="Rail",Kind="Sheet"]}[Data],
    RemovedTopRows = Table.Skip(Raw, 2),
    Headers = Table.PromoteHeaders(RemovedTopRows, [PromoteAllScalars=true]),
    Renamed = Table.RenameColumns(Headers, {{"Consignment No","ShipmentID"},{"Dispatch Date","ShipDate"},{"From Station","Origin"},{"To Station","Destination"},{"Freight Charges (PKR)","CostPKR"}}),
    Typed = Table.TransformColumnTypes(Renamed, {{"ShipmentID",Int64.Type},{"ShipDate",type date},{"Origin",type text},{"Destination",type text},{"Weight (Tons)",type number},{"CostPKR",Currency.Type},{"Status",type text}}, "en-GB"),
    ConvertedWeight = Table.AddColumn(Typed, "WeightKG", each [#"Weight (Tons)"] * 1000, type number),
    RemovedTons = Table.RemoveColumns(ConvertedWeight, {"Weight (Tons)"}),
    PrefixedIDs = Table.TransformColumns(RemovedTons, {{"ShipmentID",each "RL-" & Text.From(_, "en-GB"),type text}}),
    Cleaned = Table.TransformColumns(PrefixedIDs, {{"Status",each Text.Proper(Text.Trim(_)),type text},{"Origin",Text.Trim,type text},{"Destination",Text.Trim,type text}}),
    Tagged = Table.AddColumn(Cleaned, "SourceSystem", each "Rail", type text),
    Contract = Table.SelectColumns(Tagged, {"ShipmentID","ShipDate","Origin","Destination","WeightKG","CostPKR","Status","SourceSystem"})
in
    Contract
