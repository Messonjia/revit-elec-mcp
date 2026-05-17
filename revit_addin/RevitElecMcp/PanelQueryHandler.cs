using Autodesk.Revit.DB;
using Autodesk.Revit.UI;
using System.Text.Json;

namespace RevitElecMcp;

public class PanelQueryHandler : IExternalEventHandler
{
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

            // OST_ElectricalEquipment covers panels, switchboards, MCCs — distribution equipment
            // with circuit spaces. OST_ElectricalFixtures (used by query_elements) covers the
            // devices connected to those circuits; this query returns the panels themselves.
            var panels = new FilteredElementCollector(doc)
                .OfCategory(BuiltInCategory.OST_ElectricalEquipment)
                .WhereElementIsNotElementType()
                .ToElements()
                .Select(e => new
                {
                    id   = e.Id.Value,
                    name = e.Name,
                })
                .ToList();

            Tcs.SetResult(JsonSerializer.Serialize(panels));
        }
        catch (Exception ex)
        {
            Tcs.SetResult(JsonSerializer.Serialize(new { error = ex.Message }));
        }
    }

    public string GetName() => "RevitElecMcp.PanelQueryHandler";
}
