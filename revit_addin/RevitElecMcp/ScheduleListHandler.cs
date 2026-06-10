using Autodesk.Revit.DB;
using Autodesk.Revit.UI;
using System.Text.Json;

namespace RevitElecMcp;

// Implements the "list_schedules" command — returns every schedule in the model
// so the caller can pick one by name to pass to ScheduleExportHandler.
// Same IExternalEventHandler pattern as PanelQueryHandler: Execute() runs on the
// Revit UI thread, serialises to JSON, and signals the background thread via Tcs.
public class ScheduleListHandler : IExternalEventHandler
{
    // Tcs (TaskCompletionSource) is the handoff mechanism between threads.
    // The WebSocket background thread creates it and awaits tcs.Task.
    // Execute() — called on the UI thread — calls SetResult() when the query is done,
    // which unblocks the background thread so it can send the response.
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

            // OfClass vs OfCategory — the key distinction for schedules:
            //
            // Most Revit elements belong to a *category* (walls, fixtures, panels).
            // OfCategory(BuiltInCategory.OST_*) finds those.
            //
            // ViewSchedule is a *View* subclass — it lives in the project browser,
            // not on a floor plan. Views don't belong to a category the way model
            // elements do, so OfCategory doesn't work here.
            // OfClass(typeof(ViewSchedule)) finds elements by their C# type instead,
            // which is the correct approach for any View-derived object.
            //
            // Cast<ViewSchedule>() is needed because FilteredElementCollector returns
            // base Element objects — we cast to get access to schedule-specific members.
            var schedules = new FilteredElementCollector(doc)
                .OfClass(typeof(ViewSchedule))
                .Cast<ViewSchedule>()
                .Select(s => new
                {
                    id   = s.Id.Value,  // long (int64) in Revit 2024+ — same as circuit IDs
                    name = s.Name,      // the string shown in the Revit project browser
                })
                .OrderBy(s => s.name)   // alphabetical makes the list easier to read in Claude
                .ToList();

            Tcs.SetResult(JsonSerializer.Serialize(schedules));
        }
        catch (Exception ex)
        {
            // Always SetResult (never SetException) — the WebSocket server expects a
            // string it can forward to the caller, not an exception to propagate.
            Tcs.SetResult(JsonSerializer.Serialize(new { error = ex.Message }));
        }
    }

    // Revit writes this name to the journal file and shows it in Add-In Manager
    // diagnostics when the event fires. Useful when debugging why a handler didn't execute.
    public string GetName() => "RevitElecMcp.ScheduleListHandler";
}
