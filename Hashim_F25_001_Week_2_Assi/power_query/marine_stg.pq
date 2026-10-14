let
    Source = Csv.Document(File.Contents(DataFolder & "\marine_shipments.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Renamed = Table.RenameColumns(Headers, {{"Shipment_ID","ShipmentID"},{"Ship_Date","ShipDate"},{"Origin_Port","Origin"},{"Dest_Port","Destination"},{"Weight_KG","WeightKG"},{"Cost_PKR","CostPKR"}}),
    Typed = Table.TransformColumnTypes(Renamed, {{"ShipmentID",type text},{"ShipDate",type date},{"Origin",type text},{"Destination",type text},{"WeightKG",type number},{"CostPKR",Currency.Type},{"Status",type text}}, "en-GB"),
    Cleaned = Table.TransformColumns(Typed, {{"Status",each Text.Proper(Text.Trim(_)),type text},{"Origin",Text.Trim,type text},{"Destination",Text.Trim,type text}}),
    Tagged = Table.AddColumn(Cleaned, "SourceSystem", each "Marine", type text),
    Contract = Table.SelectColumns(Tagged, {"ShipmentID","ShipDate","Origin","Destination","WeightKG","CostPKR","Status","SourceSystem"})
in
    Contract
