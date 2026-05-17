using Autodesk.Revit.DB;
using Autodesk.Revit.DB.Electrical;
using Autodesk.Revit.UI;
using System.Text.Json;

namespace RevitElecMcp;

// Same IExternalEventHandler pattern as ElementQueryHandler — Execute() runs on the
// UI thread, reads from Revit, signals the background thread via TaskCompletionSource.
public class CircuitQueryHandler : IExternalEventHandler
{
    // PanelName is written by the WebSocket background thread before Raise() is called,
    // then read here on the UI thread. Safe because we only handle one connection at a time —
    // the background thread blocks on the TCS until we're done, so there's no race.
    public string? PanelName { get; set; }
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

            // OST_ElectricalCircuit is the category for ElectricalSystem elements —
            // the circuit objects themselves, not the physical fixtures on the circuit.
            var elements = new FilteredElementCollector(doc)
                .OfCategory(BuiltInCategory.OST_ElectricalCircuit)
                .WhereElementIsNotElementType()
                .ToElements();

            var circuits = elements
                // Cast Element → ElectricalSystem to access typed properties.
                // 'as' returns null if the cast fails instead of throwing — filter those out.
                .Select(e => e as ElectricalSystem)
                .Where(sys => sys is not null)
                // If PanelName was provided, filter to only that panel. Null means return all.
                .Where(sys => PanelName is null || sys!.PanelName == PanelName)
                .Select(sys => new
                {
                    id             = sys!.Id.Value,
                    circuit_number = sys.CircuitNumber,  // e.g. "3" — string, not int
                    panel          = sys.PanelName,
                    // ApparentLoad and Voltage are first-class typed properties on ElectricalSystem.
                    // Revit stores them in internal units: VA for load, volts for voltage.
                    apparent_load_va  = sys.ApparentLoad,
                    voltage           = sys.Voltage,
                    poles             = sys.PolesNumber,
                    // These two are not promoted to typed properties — access via parameter bag.
                    // AsDouble/AsString return 0/null if the parameter exists but has no value set.
                    breaker_rating      = sys.get_Parameter(BuiltInParameter.RBS_ELEC_CIRCUIT_RATING_PARAM)
                                           ?.AsDouble() ?? 0,
                    load_classification = sys.get_Parameter(BuiltInParameter.RBS_ELEC_LOAD_CLASSIFICATION)
                                           ?.AsString() ?? "Unknown"
                });

            Tcs.SetResult(JsonSerializer.Serialize(circuits));
        }
        catch (Exception ex)
        {
            Tcs.SetResult(JsonSerializer.Serialize(new { error = ex.Message }));
        }
    }

    public string GetName() => "RevitElecMcp.CircuitQueryHandler";
}
