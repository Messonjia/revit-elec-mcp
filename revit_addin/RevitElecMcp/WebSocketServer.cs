using Autodesk.Revit.UI;
using System.Net;
using System.Net.WebSockets;
using System.Text;
using System.Text.Json;

namespace RevitElecMcp;

public class WebSocketServer
{
    private readonly ElementQueryHandler _handler;
    private readonly ExternalEvent _externalEvent;
    private readonly HttpListener _listener;
    private CancellationTokenSource? _cts;

    public WebSocketServer(ElementQueryHandler handler, ExternalEvent externalEvent)
    {
        _handler = handler;
        _externalEvent = externalEvent;

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
        // Receive the incoming message. We don't inspect the payload yet —
        // every request returns all electrical fixtures from the active document.
        var buffer = new byte[4096];
        await ws.ReceiveAsync(buffer, CancellationToken.None);

        // Create the TCS before Raise() so Execute() always finds it set.
        var tcs = new TaskCompletionSource<string>();
        _handler.Tcs = tcs;

        // Raise() is non-blocking. It sets a flag; Revit calls Execute() on the UI
        // thread at its next idle opportunity — typically within milliseconds.
        var status = _externalEvent.Raise();
        if (status == ExternalEventRequest.Denied)
        {
            // Denied means the add-in isn't properly registered with Revit.
            // Execute() will never fire, so the TCS will never complete — send an
            // error reply now instead of hanging the socket forever.
            await SendAsync(ws, JsonSerializer.Serialize(new { error = "ExternalEvent denied — is the add-in loaded?" }));
            await ws.CloseAsync(WebSocketCloseStatus.InternalServerError, "denied", CancellationToken.None);
            return;
        }

        // Await the TCS, with a 5-second timeout in case something goes sideways
        // (e.g. Revit was in a modal dialog and never fired Execute).
        var winner = await Task.WhenAny(tcs.Task, Task.Delay(5000));
        var json = winner == tcs.Task
            ? tcs.Task.Result
            : JsonSerializer.Serialize(new { error = "Timed out waiting for Revit — was a document open?" });

        await SendAsync(ws, json);
        await ws.CloseAsync(WebSocketCloseStatus.NormalClosure, "done", CancellationToken.None);
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
