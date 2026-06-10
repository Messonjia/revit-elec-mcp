using Autodesk.Revit.UI;

namespace RevitElecMcp;

public class App : IExternalApplication
{
    private WebSocketServer? _server;

    public Result OnStartup(UIControlledApplication application)
    {
        // ExternalEvent.Create must be called on the UI thread (here in OnStartup is correct).
        // The resulting ExternalEvent object is safe to call Raise() on from any thread.
        var elementHandler = new ElementQueryHandler();
        var elementEvent   = ExternalEvent.Create(elementHandler);

        var circuitHandler = new CircuitQueryHandler();
        var circuitEvent   = ExternalEvent.Create(circuitHandler);

        var panelHandler = new PanelQueryHandler();
        var panelEvent   = ExternalEvent.Create(panelHandler);

        var breakerFixHandler = new BreakerFixHandler();
        var breakerFixEvent   = ExternalEvent.Create(breakerFixHandler);

        // Step 11: Schedule Export — two new handlers following the same pattern.
        // Each handler is paired with exactly one ExternalEvent; both must be created
        // here on the UI thread. See ScheduleListHandler.cs / ScheduleExportHandler.cs.
        var scheduleListHandler = new ScheduleListHandler();
        var scheduleListEvent   = ExternalEvent.Create(scheduleListHandler);

        var scheduleExportHandler = new ScheduleExportHandler();
        var scheduleExportEvent   = ExternalEvent.Create(scheduleExportHandler);

        _server = new WebSocketServer(
            elementHandler,       elementEvent,
            circuitHandler,       circuitEvent,
            panelHandler,         panelEvent,
            breakerFixHandler,    breakerFixEvent,
            scheduleListHandler,  scheduleListEvent,
            scheduleExportHandler, scheduleExportEvent);

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
