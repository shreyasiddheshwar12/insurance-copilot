namespace InsuranceCopilot.Client;

/// <summary>
/// The agent-facing flow, written once against <see cref="ICopilotClient"/> so it runs
/// unchanged against the real API or the mock.
/// </summary>
public sealed class RenewalWorkflow
{
    private readonly ICopilotClient _client;

    public RenewalWorkflow(ICopilotClient client) => _client = client;

    /// <summary>
    /// Asks for a renewal draft and, only if the agent approves, simulates the send.
    /// Never sends on its own: <paramref name="approve"/> is the human gate.
    /// </summary>
    public async Task<WorkflowOutcome> RunAsync(
        string customerId,
        string agentId,
        Func<Draft, Task<bool>> approve,
        CancellationToken cancellationToken = default)
    {
        var customer = await _client.GetCustomerAsync(customerId, cancellationToken).ConfigureAwait(false);

        if (!customer.HasConsent)
        {
            return new WorkflowOutcome(
                Sent: false,
                Reason: $"Consent is '{customer.ConsentStatus}'. Nothing was prepared.",
                Draft: null);
        }

        var answer = await _client.AskAsync("draft a renewal reminder", customerId, cancellationToken)
            .ConfigureAwait(false);

        if (answer.DraftId is null)
        {
            var missing = answer.MissingInputs.Any()
                ? string.Join("; ", answer.MissingInputs)
                : "no draft was produced";
            return new WorkflowOutcome(false, missing, null);
        }

        var draft = await _client.GetDraftAsync(answer.DraftId, cancellationToken).ConfigureAwait(false);

        if (!await approve(draft).ConfigureAwait(false))
        {
            return new WorkflowOutcome(false, "The agent declined the draft.", draft);
        }

        var approved = await _client.ApproveDraftAsync(draft.DraftId, agentId, cancellationToken)
            .ConfigureAwait(false);

        try
        {
            var sent = await _client.SimulateSendAsync(approved.DraftId, agentId, cancellationToken)
                .ConfigureAwait(false);
            return new WorkflowOutcome(true, "Simulated send recorded.", sent);
        }
        catch (CopilotPolicyException ex)
        {
            return new WorkflowOutcome(false, ex.Message, approved);
        }
    }

    /// <summary>Customers renewing on or before <paramref name="cutoff"/>, soonest first.</summary>
    public static IReadOnlyList<Customer> DueBy(IEnumerable<Customer> customers, DateOnly cutoff) =>
        customers
            .Where(c => DateOnly.TryParse(c.RenewalDate, out var due) && due <= cutoff)
            .OrderBy(c => DateOnly.Parse(c.RenewalDate))
            .ThenBy(c => c.CustomerId, StringComparer.Ordinal)
            .ToList();

    /// <summary>How many customers sit in each consent state, for the operations dashboard.</summary>
    public static IReadOnlyDictionary<string, int> ConsentBreakdown(IEnumerable<Customer> customers) =>
        customers
            .GroupBy(c => c.ConsentStatus)
            .ToDictionary(g => g.Key, g => g.Count(), StringComparer.Ordinal);
}

public sealed record WorkflowOutcome(bool Sent, string Reason, Draft? Draft);
