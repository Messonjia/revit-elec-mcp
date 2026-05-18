using Autodesk.Revit.DB;
using Autodesk.Revit.DB.Electrical;
using Autodesk.Revit.UI;
using System.Text.Json;

namespace RevitElecMcp;

public class BreakerFixHandler : IExternalEventHandler
{
    // Background thread writes these before Raise(); Execute() reads them on the UI thread.
    public long   CircuitId { get; set; }
    public double NewRating { get; set; }   // amps, as supplied by the caller
    public TaskCompletionSource<string>? Tcs { get; set; }

    public void Execute(UIApplication app)
    {
        if (Tcs is null) return;

        try
        {
            var doc = app.ActiveUIDocument?.Document;
            if (doc is null)
            {
                Tcs.SetResult(JsonSerializer.Serialize(new { error = "No active Revit document" }));
                return;
            }

            // Resolve the element by ID and confirm it's actually an electrical circuit.
            // 'is not' pattern match both checks the type and binds the variable in one line.
            var element = doc.GetElement(new ElementId(CircuitId));
            if (element is not ElectricalSystem circuit)
            {
                Tcs.SetResult(JsonSerializer.Serialize(
                    new { error = $"Element {CircuitId} is not an electrical circuit" }));
                return;
            }

            var param = circuit.get_Parameter(BuiltInParameter.RBS_ELEC_CIRCUIT_RATING_PARAM);
            if (param is null || param.IsReadOnly)
            {
                Tcs.SetResult(JsonSerializer.Serialize(
                    new { error = "Breaker rating parameter is missing or read-only on this circuit" }));
                return;
            }

            // Transaction scope: Start → write → Commit.
            // The 'using' ensures Dispose() is called if an exception is thrown, which
            // abandons the transaction (same effect as RollBack) before catch runs.
            using var tx = new Transaction(doc, "Fix breaker size");
            tx.Start();

            // Set() takes internal units — same rule as reads. Convert explicitly.
            param.Set(UnitUtils.ConvertToInternalUnits(NewRating, UnitTypeId.Amperes));

            var commitStatus = tx.Commit();
            if (commitStatus != TransactionStatus.Committed)
                throw new InvalidOperationException($"Commit failed with status: {commitStatus}");

            Tcs.SetResult(JsonSerializer.Serialize(new
            {
                success    = true,
                circuit_id = CircuitId,
                new_rating = NewRating,
                message    = $"Breaker rating updated to {NewRating}A. Undo with Ctrl+Z in Revit."
            }));
        }
        catch (Exception ex)
        {
            // By the time we reach here, the 'using' has already disposed (abandoned) the
            // transaction if it was open — no explicit RollBack needed in the catch.
            Tcs.SetResult(JsonSerializer.Serialize(new { error = ex.Message }));
        }
    }

    public string GetName() => "RevitElecMcp.BreakerFixHandler";
}
