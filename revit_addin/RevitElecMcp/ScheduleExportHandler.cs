using Autodesk.Revit.DB;
using Autodesk.Revit.UI;
using System.Text.Json;

namespace RevitElecMcp;

// Implements the "export_schedule" command — reads a named schedule's table data
// and returns it as { schedule_name, columns: [...], rows: [[...], ...] }.
public class ScheduleExportHandler : IExternalEventHandler
{
    // ScheduleName is written by the WebSocket background thread before Raise() is called,
    // then read here on the UI thread. This is safe because only one WebSocket connection
    // is processed at a time — the background thread blocks on Tcs.Task until Execute()
    // finishes, so there is no race between writing ScheduleName and reading it.
    public string? ScheduleName { get; set; }
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

            // Find the schedule by exact name match. Names in Revit are case-sensitive and
            // must match the project browser label exactly (e.g. "Panel Schedule - LP-1").
            // list_schedules returns the canonical names so the caller can get the right string.
            var schedule = new FilteredElementCollector(doc)
                .OfClass(typeof(ViewSchedule))
                .Cast<ViewSchedule>()
                .FirstOrDefault(s => s.Name == ScheduleName);

            if (schedule is null)
            {
                Tcs.SetResult(JsonSerializer.Serialize(new { error = $"Schedule not found: '{ScheduleName}'" }));
                return;
            }

            // GetTableData() returns a ScheduleTableData object that represents the schedule
            // as a grid. The grid is split into named sections; we need two of them:
            //   SectionType.Header — the column title row(s) at the top
            //   SectionType.Body   — the data rows below the header
            // There is also SectionType.Footer (totals row) which we skip.
            var tableData = schedule.GetTableData();

            // --- Column names (from the Header section) ---
            // The header section contains at least one row: row 0 is always the column titles
            // (the names you see in bold at the top of the schedule in Revit).
            // Checking NumberOfRows > 0 guards against a degenerate schedule with no header,
            // though in practice Revit always creates one.
            var headerSection = tableData.GetSectionData(SectionType.Header);
            var columns = new List<string>();
            if (headerSection.NumberOfRows > 0)
            {
                // GetCellText(row, col) returns a pre-formatted string exactly as Revit
                // would display it on screen — e.g. "20 A", not the raw double 20.0.
                // This is intentional: a schedule is a *presentation view*, not raw data.
                // The caller (Claude) receives formatted strings and can parse them if needed.
                for (int col = 0; col < headerSection.NumberOfColumns; col++)
                    columns.Add(headerSection.GetCellText(0, col));
            }

            // --- Data rows (from the Body section) ---
            // Unlike most .NET collection access, GetCellText *throws* an exception if row
            // or col is out of range — it does NOT return null or an empty string.
            // If we hardcoded a row or column count and the schedule changed, we'd get
            // an exception at runtime. Always read NumberOfRows / NumberOfColumns first
            // and use them as the loop bounds.
            var bodySection = tableData.GetSectionData(SectionType.Body);
            var rows = new List<List<string>>();
            for (int row = 0; row < bodySection.NumberOfRows; row++)
            {
                var rowData = new List<string>();
                for (int col = 0; col < bodySection.NumberOfColumns; col++)
                    rowData.Add(bodySection.GetCellText(row, col));
                rows.Add(rowData);
            }

            // Return shape mirrors a simple tabular format:
            //   columns: ["Circuit Number", "Load Name", "Frame"]
            //   rows:    [["1", "Lighting", "20 A"], ["3", "Receptacles", "20 A"], ...]
            // The column list lets Claude (or any consumer) build a header-keyed dict per row.
            Tcs.SetResult(JsonSerializer.Serialize(new
            {
                schedule_name = schedule.Name,
                columns,
                rows,
            }));
        }
        catch (Exception ex)
        {
            Tcs.SetResult(JsonSerializer.Serialize(new { error = ex.Message }));
        }
    }

    public string GetName() => "RevitElecMcp.ScheduleExportHandler";
}
