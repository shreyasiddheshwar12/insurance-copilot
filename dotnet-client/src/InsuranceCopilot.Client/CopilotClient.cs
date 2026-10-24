using System.Net;
using System.Net.Http.Json;
using System.Text.Json;

namespace InsuranceCopilot.Client;

/// <summary>
/// HTTP implementation. The <see cref="HttpClient"/> is injected rather than constructed, so it
/// comes from IHttpClientFactory with pooled, correctly disposed handlers.
/// </summary>
public sealed class CopilotClient : ICopilotClient
{
    private static readonly JsonSerializerOptions JsonOptions = new(JsonSerializerDefaults.Web);

    private readonly HttpClient _http;

    public CopilotClient(HttpClient http) => _http = http;

    public Task<Customer> GetCustomerAsync(string customerId, CancellationToken cancellationToken = default)
        => SendAsync<Customer>(HttpMethod.Get, $"/customers/{customerId}", null, cancellationToken);

    public Task<AskResult> AskAsync(string message, string? customerId = null, CancellationToken cancellationToken = default)
        => SendAsync<AskResult>(
            HttpMethod.Post,
            "/ask",
            new { message, customer_id = customerId },
            cancellationToken);

    public Task<Draft> GetDraftAsync(string draftId, CancellationToken cancellationToken = default)
        => SendAsync<Draft>(HttpMethod.Get, $"/drafts/{draftId}", null, cancellationToken);

    public Task<Draft> ApproveDraftAsync(string draftId, string agentId, CancellationToken cancellationToken = default)
        => SendAsync<Draft>(
            HttpMethod.Post,
            $"/drafts/{draftId}/approve",
            new { agent_id = agentId },
            cancellationToken);

    public Task<Draft> SimulateSendAsync(string draftId, string agentId, CancellationToken cancellationToken = default)
        => SendAsync<Draft>(
            HttpMethod.Post,
            $"/drafts/{draftId}/send",
            new { agent_id = agentId },
            cancellationToken);

    private async Task<T> SendAsync<T>(
        HttpMethod method,
        string path,
        object? body,
        CancellationToken cancellationToken)
    {
        using var request = new HttpRequestMessage(method, path);
        if (body is not null)
        {
            request.Content = JsonContent.Create(body, options: JsonOptions);
        }

        using var response = await _http.SendAsync(request, cancellationToken).ConfigureAwait(false);

        if (!response.IsSuccessStatusCode)
        {
            throw await BuildExceptionAsync(response, cancellationToken).ConfigureAwait(false);
        }

        var result = await response.Content
            .ReadFromJsonAsync<T>(JsonOptions, cancellationToken)
            .ConfigureAwait(false);

        return result ?? throw new CopilotPolicyException(
            $"The API returned an empty body for {path}.",
            (int)response.StatusCode);
    }

    private static async Task<Exception> BuildExceptionAsync(
        HttpResponseMessage response,
        CancellationToken cancellationToken)
    {
        var status = (int)response.StatusCode;
        var detail = await ReadDetailAsync(response, cancellationToken).ConfigureAwait(false);

        // 403 and 409 are the API's deliberate policy refusals (no approval, no consent).
        return response.StatusCode is HttpStatusCode.Forbidden or HttpStatusCode.Conflict
            ? new CopilotPolicyException(detail, status)
            : new HttpRequestException($"{status}: {detail}");
    }

    private static async Task<string> ReadDetailAsync(
        HttpResponseMessage response,
        CancellationToken cancellationToken)
    {
        try
        {
            var payload = await response.Content
                .ReadFromJsonAsync<Dictionary<string, JsonElement>>(JsonOptions, cancellationToken)
                .ConfigureAwait(false);

            if (payload is not null
                && payload.TryGetValue("detail", out var detail)
                && detail.ValueKind == JsonValueKind.String)
            {
                return detail.GetString() ?? response.ReasonPhrase ?? "Request failed.";
            }
        }
        catch (JsonException)
        {
            // Fall through: the body was not the JSON shape we expected.
        }

        return response.ReasonPhrase ?? "Request failed.";
    }
}
