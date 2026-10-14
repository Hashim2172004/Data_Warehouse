let
    Appended = Table.Combine({marine_stg,rail_stg,road_stg}),
    Contract = Table.SelectColumns(Appended, {"ShipmentID","ShipDate","Origin","Destination","WeightKG","CostPKR","Status","SourceSystem"}),
    Typed = Table.TransformColumnTypes(Contract, {{"ShipmentID",type text},{"ShipDate",type date},{"Origin",type text},{"Destination",type text},{"WeightKG",type number},{"CostPKR",Currency.Type},{"Status",type text},{"SourceSystem",type text}}),
    Keys = Table.Column(Typed,"ShipmentID"),
    Dates = Table.Column(Typed,"ShipDate"),
    Weights = Table.Column(Typed,"WeightKG"),
    Validated = if Table.RowCount(Typed) = 34 and List.Sum(Weights) = 578650 and List.NonNullCount(Keys) = 34 and not List.Contains(Keys, "") and List.Count(List.Distinct(Keys)) = 34 and List.NonNullCount(Dates) = 34 and List.NonNullCount(Weights) = 34 and List.Count(List.Distinct(Table.Column(Typed,"Status"))) = 3
                then Typed else error "Shipment validation failed: check sources, exclusions, units and dates."
in
    Validated
