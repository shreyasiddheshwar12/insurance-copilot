namespace InsuranceCopilot.Client;

/// <summary>
/// The copilot API as the .NET side sees it. Two implementations exist behind this interface
/// (<see cref="CopilotClient"/> over HTTP and <see cref="MockCopilotClient"/> in memory), so
/// callers and tests can swap providers through dependency injection without code changes.
/// </summary>
public interface ICopilotClient
{
    Task<Customer> GetCustomerAsync(string customerId, CancellationToken cancellationToken = default);

    Task<AskResult> AskAsync(string message, string? customerId = null, CancellationToken cancellationToken = default);

    Task<Draft> GetDraftAsync(string draftId, CancellationToken cancellationToken = default);

    /// <summary>Records that a named agent reviewed the draft. Required before any send.</summary>
    Task<Draft> ApproveDraftAsync(string draftId, string agentId, CancellationToken cancellationToken = default);

    /// <summary>Simulated send only. Throws <see cref="CopilotPolicyException"/> without approval or consent.</summary>
    Task<Draft> SimulateSendAsync(string draftId, string agentId, CancellationToken cancellationToken = default);
}
