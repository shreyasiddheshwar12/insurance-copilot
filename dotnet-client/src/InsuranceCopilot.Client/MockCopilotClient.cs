using System.Collections.Concurrent;

namespace InsuranceCopilot.Client;

/// <summary>
/// In-memory stand-in used by unit tests and by the demo when the Python API is not running.
/// It enforces the same two rules as the real service: a send needs an approval and opt-in
/// consent. Keeping the rules here as well means a test against the fake cannot pass for a
/// reason the real service would reject.
/// </summary>
public sealed class MockCopilotClient : ICopilotClient
{
    private readonly ConcurrentDictionary<string, Customer> _customers = new();
    private readonly ConcurrentDictionary<string, Draft> _drafts = new();
    private int _counter;

    public MockCopilotClient()
    {
        Add(new Customer
        {
            CustomerId = "C-204",
            City = "Pune",
            RenewalDate = "2026-12-04",
            ConsentStatus = "opt_in",
            FictionalPlanId = "GOLD",
        });

        Add(new Customer
        {
            CustomerId = "C-999",
            City = "Mumbai",
            RenewalDate = "2026-11-18",
            ConsentStatus = "opt_out",
            FictionalPlanId = "SILVER",
        });
    }

    public void Add(Customer customer) => _customers[customer.CustomerId] = customer;

    public Task<Customer> GetCustomerAsync(string customerId, CancellationToken cancellationToken = default)
        => _customers.TryGetValue(customerId, out var customer)
            ? Task.FromResult(customer)
            : Task.FromException<Customer>(
                new CopilotPolicyException($"customer {customerId} not found", 404));

    public Task<AskResult> AskAsync(string message, string? customerId = null, CancellationToken cancellationToken = default)
    {
        if (customerId is null || !_customers.TryGetValue(customerId, out var customer))
        {
            return Task.FromResult(new AskResult
            {
                Intents = new[] { "unclear" },
                MissingInputs = new[] { "customer_id (for example C-204)" },
            });
        }

        if (!customer.HasConsent)
        {
            return Task.FromResult(new AskResult
            {
                Intents = new[] { "renewal" },
                AnswerParts = new[] { $"{customer.CustomerId} renews on {customer.RenewalDate}." },
                Warnings = new[] { $"Consent is '{customer.ConsentStatus}'. No send is allowed." },
            });
        }

        var draft = new Draft
        {
            DraftId = $"D-mock{Interlocked.Increment(ref _counter):000}",
            CustomerId = customer.CustomerId,
            TemplateId = "RENEWAL_REMINDER_V1",
            Text = $"Hello {customer.CustomerId}, your fictional plan renews on {customer.RenewalDate}.",
            Citations = new[] { "TEMPLATE:RENEWAL_REMINDER_V1@2026.1" },
            Status = "pending_approval",
        };
        _drafts[draft.DraftId] = draft;

        return Task.FromResult(new AskResult
        {
            Intents = new[] { "renewal" },
            AnswerParts = new[]
            {
                $"{customer.CustomerId} renews on {customer.RenewalDate}.",
                $"Reminder draft {draft.DraftId} is saved and waits for your approval.",
            },
            Citations = draft.Citations,
            DraftId = draft.DraftId,
        });
    }

    public Task<Draft> GetDraftAsync(string draftId, CancellationToken cancellationToken = default)
        => _drafts.TryGetValue(draftId, out var draft)
            ? Task.FromResult(draft)
            : Task.FromException<Draft>(new CopilotPolicyException($"draft {draftId} not found", 404));

    public async Task<Draft> ApproveDraftAsync(string draftId, string agentId, CancellationToken cancellationToken = default)
    {
        if (string.IsNullOrWhiteSpace(agentId))
        {
            throw new CopilotPolicyException("an agent_id is required to approve a draft", 409);
        }

        var draft = await GetDraftAsync(draftId, cancellationToken).ConfigureAwait(false);
        if (!draft.AwaitingApproval)
        {
            throw new CopilotPolicyException($"draft {draftId} is '{draft.Status}', not pending approval", 409);
        }

        var approved = draft with { Status = "approved", ApprovedBy = agentId.Trim() };
        _drafts[draftId] = approved;
        return approved;
    }

    public async Task<Draft> SimulateSendAsync(string draftId, string agentId, CancellationToken cancellationToken = default)
    {
        var draft = await GetDraftAsync(draftId, cancellationToken).ConfigureAwait(false);

        if (string.IsNullOrWhiteSpace(agentId))
        {
            throw new CopilotPolicyException("sending requires an explicit agent approval", 403);
        }

        if (draft.Status != "approved" || string.IsNullOrEmpty(draft.ApprovedBy))
        {
            throw new CopilotPolicyException("sending is blocked until an agent approves the draft", 403);
        }

        if (!_customers.TryGetValue(draft.CustomerId, out var customer) || !customer.HasConsent)
        {
            throw new CopilotPolicyException("sending is blocked: consent is not opt_in", 403);
        }

        var sent = draft with
        {
            Status = "simulated_sent",
            SimulatedSentAt = DateTimeOffset.UtcNow.ToString("yyyy-MM-ddTHH:mm:sszzz"),
        };
        _drafts[draftId] = sent;
        return sent;
    }
}
