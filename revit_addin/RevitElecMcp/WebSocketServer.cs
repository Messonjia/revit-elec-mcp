using Autodesk.Revit.UI;
using System.Net;
using System.Net.WebSockets;
using System.Text;
using System.Text.Json;

namespace RevitElecMcp;

public class WebSocketServer
{
    private readonly ElementQueryHandler _elementHandler;
    private readonly ExternalEvent _elementEvent;
    private readonly CircuitQueryHandler _circuitHandler;
    private readonly ExternalEvent _circuitEvent;
    private readonly PanelQueryHandler _panelHandler;
    private readonly ExternalEvent _panelEvent;
    private readonly BreakerFixHandler _breakerFixHandler;
    private readonly ExternalEvent _breakerFixEvent;
    private readonly HttpListener _listener;
    private CancellationTokenSource? _cts;

    public WebSocketServer(
        ElementQueryHandler elementHandler, ExternalEvent elementEvent,
        CircuitQueryHandler circuitHandler,  ExternalEvent circuitEvent,
        PanelQueryHandler panelHandler,      ExternalEvent panelEvent,
        BreakerFixHandler breakerFixHandler, ExternalEvent breakerFixEvent)
    {
        _elementHandler    = elementHandler;
        _elementEvent      = elementEvent;
        _circuitHandler    = circuitHandler;
        _circuitEvent      = circuitEvent;
        _panelHandler      = panelHandler;
        _panelEvent        = panelEvent;
        _breakerFixHandler = breakerFixHandler;
        _breakerFixEvent   = breakerFixEvent;

        // HttpListener is .NET's built-in HTTP/WebSocket server — no NuGet needed.
        // The trailing slash is required by HttpListener; omitting it throws at Start().
        _listener = new HttpListener();
        _listener.Prefixes.Add("http://localhost:8765/");
    }

    public async Task StartAsync()
    {
        _cts = new CancellationTokenSource();
        _listener.Start();

        while (!_cts.Token.IsCancellationRequested)
        {
            HttpListenerContext context;
            try
            {
                // GetContextAsync blocks until an HTTP request arrives.
                // When Stop() is called, this throws HttpListenerException — caught below.
                context = await _listener.GetContextAsync();
            }
            catch (HttpListenerException) when (_cts.Token.IsCancellationRequested)
            {
                break; // Normal shutdown.
            }

            if (!context.Request.IsWebSocketRequest)
            {
                context.Response.StatusCode = 400;
                context.Response.Close();
                continue;
            }

            // Upgrade the HTTP connection to WebSocket.
            // subProtocol: null because the Python websockets library doesn't set one.
            var wsContext = await context.AcceptWebSocketAsync(subProtocol: null);
            await HandleConnectionAsync(wsContext.WebSocket);
        }
    }

    private async Task HandleConnectionAsync(WebSocket ws)
    {
        var buffer   = new byte[4096];
        // ReceiveAsync returns a result object — Count tells us how many bytes actually arrived.
        // Previously we ignored this and passed the whole buffer to handlers, which included
        // trailing zero bytes. GetString with the correct count fixes that.
        var received = await ws.ReceiveAsync(buffer, CancellationToken.None);
        var message  = Encoding.UTF8.GetString(buffer, 0, received.Count);

        string json;
        try
        {
            using var doc = JsonDocument.Parse(message);
            var command = doc.RootElement.GetProperty("command").GetString();

            // Option A routing: switch on command string.
            // Each arm calls a private method that sets handler state, raises the event,
            // and awaits the result. The shared raise+wait logic lives in RaiseAndWaitAsync.
            json = command switch
            {
                "get_elements" => await HandleGetElementsAsync(),
                "get_circuits" => await HandleGetCircuitsAsync(
                    doc.RootElement.GetProperty("panel").GetString()),
                "list_panels"  => await HandleGetPanelsAsync(),
                "fix_breaker"  => await HandleFixBreakerAsync(
                    doc.RootElement.GetProperty("circuit_id").GetInt64(),
                    doc.RootElement.GetProperty("new_rating").GetDouble()),
                _ => JsonSerializer.Serialize(new { error = $"Unknown command: {command}" })
            };
        }
        catch (Exception ex)
        {
            // Catches malformed JSON, missing "command" property, or unknown property access.
            json = JsonSerializer.Serialize(new { error = $"Bad request: {ex.Message}" });
        }

        await SendAsync(ws, json);
        await ws.CloseAsync(WebSocketCloseStatus.NormalClosure, "done", CancellationToken.None);
    }

    private async Task<string> HandleGetElementsAsync()
    {
        var tcs = new TaskCompletionSource<string>();
        _elementHandler.Tcs = tcs;
        return await RaiseAndWaitAsync(_elementEvent, tcs);
    }

    private async Task<string> HandleGetCircuitsAsync(string? panelName)
    {
        var tcs = new TaskCompletionSource<string>();
        _circuitHandler.PanelName = panelName;
        _circuitHandler.Tcs       = tcs;
        return await RaiseAndWaitAsync(_circuitEvent, tcs);
    }

    private async Task<string> HandleGetPanelsAsync()
    {
        var tcs = new TaskCompletionSource<string>();
        _panelHandler.Tcs = tcs;
        return await RaiseAndWaitAsync(_panelEvent, tcs);
    }

    private async Task<string> HandleFixBreakerAsync(long circuitId, double newRating)
    {
        var tcs = new TaskCompletionSource<string>();
        _breakerFixHandler.CircuitId = circuitId;
        _breakerFixHandler.NewRating = newRating;
        _breakerFixHandler.Tcs       = tcs;
        return await RaiseAndWaitAsync(_breakerFixEvent, tcs);
    }

    // Every handler follows the same raise → check denied → await with timeout pattern.
    // Extracting it here means adding a new command only requires a new Handle*Async method,
    // not duplicating this boilerplate.
    private static async Task<string> RaiseAndWaitAsync(ExternalEvent evt, TaskCompletionSource<string> tcs)
    {
        var status = evt.Raise();
        if (status == ExternalEventRequest.Denied)
            return JsonSerializer.Serialize(new { error = "ExternalEvent denied — is the add-in loaded?" });

        var winner = await Task.WhenAny(tcs.Task, Task.Delay(5000));
        return winner == tcs.Task
            ? tcs.Task.Result
            : JsonSerializer.Serialize(new { error = "Timed out waiting for Revit — was a document open?" });
    }

    private static async Task SendAsync(WebSocket ws, string message)
    {
        var bytes = Encoding.UTF8.GetBytes(message);
        // endOfMessage: true — we always send the whole payload in one frame.
        await ws.SendAsync(bytes, WebSocketMessageType.Text, endOfMessage: true, CancellationToken.None);
    }

    public void Stop()
    {
        _cts?.Cancel();
        _listener.Stop(); // Causes the blocked GetContextAsync to throw, exiting the loop.
    }
}
