using Autodesk.Revit.UI;

namespace RevitElecMcp;

public class App : IExternalApplication
{
    private WebSocketServer? _server;

    public Result OnStartup(UIControlledApplication application)
    {
        // ExternalEvent.Create must be called on the UI thread (here in OnStartup is correct).
        // The resulting ExternalEvent object is safe to call Raise() on from any thread.
        var handler = new ElementQueryHandler();
        var externalEvent = ExternalEvent.Create(handler);

        _server = new WebSocketServer(handler, externalEvent);

        // Start the WebSocket listener on a background thread — if we awaited it here,
        // OnStartup would block and Revit would hang on startup.
        Task.Run(() => _server.StartAsync());

        return Result.Succeeded;
    }

    public Result OnShutdown(UIControlledApplication application)
    {
        // Stop() cancels the listener loop and closes the HttpListener.
        _server?.Stop();
        return Result.Succeeded;
    }
}
