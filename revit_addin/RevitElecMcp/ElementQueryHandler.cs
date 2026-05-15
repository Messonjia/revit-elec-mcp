using Autodesk.Revit.DB;
using Autodesk.Revit.UI;
using System.Text.Json;

namespace RevitElecMcp;

// IExternalEventHandler is the interface Revit requires for anything that wants
// to call the Revit API from outside the UI thread. Revit calls Execute() for you —
// on the UI thread, at a moment it considers safe. You never call Execute() directly.
public class ElementQueryHandler : IExternalEventHandler
{
    // Shared state between the WebSocket background thread and the Revit UI thread.
    // The background thread writes a fresh TCS here before calling Raise(),
    // then awaits it. Execute() reads it and calls SetResult() to unblock the awaiter.
    public TaskCompletionSource<string>? Tcs { get; set; }

    public void Execute(UIApplication app)
    {
        // Revit called us — we are on the UI thread. Revit API calls are valid here.
        if (Tcs is null) return;

        try
        {
            var doc = app.ActiveUIDocument?.Document;
            if (doc is null)
            {
                Tcs.SetResult(JsonSerializer.Serialize(new { error = "No active Revit document" }));
                return;
            }

            // FilteredElementCollector is the standard Revit query API.
            // OfCategory limits to electrical fixtures (lights, receptacles, panels, etc.).
            // WhereElementIsNotElementType excludes family type definitions — we want instances only.
            var elements = new FilteredElementCollector(doc)
                .OfCategory(BuiltInCategory.OST_ElectricalFixtures)
                .WhereElementIsNotElementType()
                .ToElements();

            var result = elements.Select(e => new
            {
                id = e.Id.Value,   // ElementId.Value returns long (Revit 2024+; IntegerValue is deprecated)
                name = e.Name,
            });

            Tcs.SetResult(JsonSerializer.Serialize(result));
        }
        catch (Exception ex)
        {
            // Use SetResult with error JSON rather than SetException — the WebSocket server
            // needs a string it can send back, not an exception to propagate.
            Tcs.SetResult(JsonSerializer.Serialize(new { error = ex.Message }));
        }
    }

    // GetName appears in Revit's journal file and Add-In Manager diagnostics.
    public string GetName() => "RevitElecMcp.ElementQueryHandler";
}
