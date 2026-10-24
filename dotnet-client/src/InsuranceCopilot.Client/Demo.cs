using Microsoft.Extensions.DependencyInjection;

namespace InsuranceCopilot.Client;

/// <summary>
/// Console entry point showing async calls and DI end to end.
///
///   dotnet run --project src/InsuranceCopilot.Client            (talks to the Python API)
///   dotnet run --project src/InsuranceCopilot.Client -- --mock  (no API needed)
/// </summary>
public static class Demo
{
    public static async Task<int> Main(string[] args)
    {
        var useMock = args.Contains("--mock", StringComparer.OrdinalIgnoreCase);
        var customerId = args.FirstOrDefault(a => a.StartsWith("C-", StringComparison.Ordinal)) ?? "C-204";

        var services = new ServiceCollection()
            .AddCopilotClient(options =>
            {
                options.Provider = useMock ? CopilotProvider.Mock : CopilotProvider.Http;
                options.BaseUrl = Environment.GetEnvironmentVariable("COPILOT_BASE_URL") ?? "http://127.0.0.1:8000";
            })
            .BuildServiceProvider();

        var client = services.GetRequiredService<ICopilotClient>();
        var workflow = new RenewalWorkflow(client);

        Console.WriteLine($"Provider: {(useMock ? "mock" : "http")}   Customer: {customerId}");
        Console.WriteLine(new string('-', 60));

        try
        {
            var outcome = await workflow.RunAsync(
                customerId,
                agentId: "dotnet-demo-agent",
                approve: draft =>
                {
                    // The human gate. A real console app would prompt here.
                    Console.WriteLine($"Draft {draft.DraftId}: {draft.Text}");
                    Console.WriteLine($"Citations: {string.Join(", ", draft.Citations)}");
                    Console.WriteLine("Approving as the agent...");
                    return Task.FromResult(true);
                });

            Console.WriteLine(new string('-', 60));
            Console.WriteLine($"Sent (simulated): {outcome.Sent}");
            Console.WriteLine($"Reason: {outcome.Reason}");
            return 0;
        }
        catch (CopilotPolicyException ex)
        {
            Console.Error.WriteLine($"Policy refusal ({ex.StatusCode}): {ex.Message}");
            return 2;
        }
        catch (HttpRequestException ex)
        {
            Console.Error.WriteLine($"Could not reach the API: {ex.Message}");
            Console.Error.WriteLine("Start it with: uvicorn copilot.api:app  (or pass --mock)");
            return 1;
        }
    }
}
