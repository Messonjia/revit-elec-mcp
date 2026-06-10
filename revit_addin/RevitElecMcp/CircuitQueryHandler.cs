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
                .Select(sys =>
                {
                    // ApparentLoad and Voltage are in Revit internal units — must convert before returning.
                    double loadVA = UnitUtils.ConvertFromInternalUnits(sys!.ApparentLoad, UnitTypeId.VoltAmperes);
                    double volts  = UnitUtils.ConvertFromInternalUnits(sys.Voltage, UnitTypeId.Volts);

                    // RBS_ELEC_LOAD_CLASSIFICATION is stored as an ElementId reference to a
                    // LoadClassification element, not a plain string — AsString() always returns null.
                    var lcParam   = sys.get_Parameter(BuiltInParameter.RBS_ELEC_LOAD_CLASSIFICATION);
                    string lcName = "Unknown";
                    if (lcParam?.StorageType == StorageType.ElementId)
                        lcName = doc.GetElement(lcParam.AsElementId())?.Name ?? "Unknown";
                    else if (lcParam?.StorageType == StorageType.String)
                        lcName = lcParam.AsString() ?? "Unknown";

                    // For motor/HVAC circuits only, look for HP on each connected element.
                    // RBS_ELEC_MOTOR_SIZE does not exist in the Revit 2025 BuiltInParameter enum —
                    // use LookupParameter by name instead. "Motor Size" is the standard parameter
                    // name in Revit MEP equipment families; returns null when absent, which causes
                    // check_circuit to fall back to manual_review.
                    double? hp = null;
                    if (lcName == "Motor" || lcName == "HVAC")
                    {
                        foreach (Element connectedEl in sys.Elements)
                        {
                            var hpParam = connectedEl.LookupParameter("Motor Size");
                            if (hpParam is { StorageType: StorageType.Double } && hpParam.AsDouble() > 0)
                            {
                                hp = hpParam.AsDouble();
                                break; // take HP from the first element that has it
                            }
                        }
                    }

                    return new
                    {
                        id                  = sys.Id.Value,
                        circuit_number      = sys.CircuitNumber,  // string, e.g. "3"
                        panel               = sys.PanelName,
                        apparent_load_va    = loadVA,
                        voltage             = volts,
                        poles               = sys.PolesNumber,
                        // A circuit with no connected elements is a spare — skip NEC sizing.
                        is_spare            = sys.Elements.Size == 0,
                        breaker_rating      = sys.get_Parameter(BuiltInParameter.RBS_ELEC_CIRCUIT_RATING_PARAM)
                                               ?.AsDouble() ?? 0,
                        load_classification = lcName,
                        hp                  = hp   // null if not a motor/HVAC circuit or HP not found
                    };
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
