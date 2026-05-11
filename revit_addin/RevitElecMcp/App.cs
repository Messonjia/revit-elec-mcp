using Autodesk.Revit.UI;

namespace RevitElecMcp;

// Revit instantiates this class because FullClassName in RevitElecMcp.addin points here.
// IExternalApplication requires exactly two methods: OnStartup and OnShutdown.
public class App : IExternalApplication
{
    public Result OnStartup(UIControlledApplication application)
    {
        // UIControlledApplication is a restricted view of Revit — you can subscribe
        // to events and add ribbon buttons, but you cannot open documents here.
        // Revit is still initializing when OnStartup runs.

        // TaskDialog is Revit's native modal popup. Using it here confirms the DLL
        // loaded and this method ran. Replace with logging before shipping.
        TaskDialog.Show("RevitElecMcp", "Add-in loaded successfully.");

        // Result.Succeeded tells Revit the startup completed without error.
        // Returning Result.Failed causes Revit to unload the add-in and show a warning.
        return Result.Succeeded;
    }

    public Result OnShutdown(UIControlledApplication application)
    {
        // Nothing to clean up yet — WebSocket server teardown comes in Step 7.4.
        return Result.Succeeded;
    }
}
