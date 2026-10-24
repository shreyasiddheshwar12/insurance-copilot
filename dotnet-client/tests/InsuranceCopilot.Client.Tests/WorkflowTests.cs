using InsuranceCopilot.Client;
using Xunit;

namespace InsuranceCopilot.Client.Tests;

public class WorkflowTests
{
    private static RenewalWorkflow Build(out MockCopilotClient mock)
    {
        mock = new MockCopilotClient();
        return new RenewalWorkflow(mock);
    }

    [Fact]
    public async Task ApprovedOptInCustomerReachesSimulatedSend()
    {
        var workflow = Build(out _);

        var outcome = await workflow.RunAsync("C-204", "agent-1", _ => Task.FromResult(true));

        Assert.True(outcome.Sent);
        Assert.Equal("simulated_sent", outcome.Draft?.Status);
        Assert.Equal("agent-1", outcome.Draft?.ApprovedBy);
    }

    [Fact]
    public async Task OptOutCustomerIsStoppedBeforeAnyDraft()
    {
        var workflow = Build(out _);

        var outcome = await workflow.RunAsync("C-999", "agent-1", _ => Task.FromResult(true));

        Assert.False(outcome.Sent);
        Assert.Null(outcome.Draft);
        Assert.Contains("opt_out", outcome.Reason);
    }

    [Fact]
    public async Task DecliningTheDraftSendsNothing()
    {
        var workflow = Build(out var mock);

        var outcome = await workflow.RunAsync("C-204", "agent-1", _ => Task.FromResult(false));

        Assert.False(outcome.Sent);
        Assert.NotNull(outcome.Draft);

        var stored = await mock.GetDraftAsync(outcome.Draft!.DraftId);
        Assert.Equal("pending_approval", stored.Status);
    }

    [Fact]
    public async Task SendWithoutApprovalIsRefused()
    {
        var mock = new MockCopilotClient();
        var answer = await mock.AskAsync("draft a renewal reminder", "C-204");

        var ex = await Assert.ThrowsAsync<CopilotPolicyException>(
            () => mock.SimulateSendAsync(answer.DraftId!, "agent-1"));

        Assert.Equal(403, ex.StatusCode);
    }

    [Fact]
    public async Task SendWithoutAnAgentIdIsRefused()
    {
        var mock = new MockCopilotClient();
        var answer = await mock.AskAsync("draft a renewal reminder", "C-204");
        await mock.ApproveDraftAsync(answer.DraftId!, "agent-1");

        await Assert.ThrowsAsync<CopilotPolicyException>(
            () => mock.SimulateSendAsync(answer.DraftId!, "   "));
    }

    [Fact]
    public async Task AskWithoutACustomerNamesTheMissingInput()
    {
        var mock = new MockCopilotClient();

        var answer = await mock.AskAsync("draft a renewal reminder");

        Assert.Null(answer.DraftId);
        Assert.NotEmpty(answer.MissingInputs);
    }

    [Fact]
    public void DueByReturnsOnlyCustomersOnOrBeforeTheCutoffSortedByDate()
    {
        var customers = new[]
        {
            new Customer { CustomerId = "C-003", RenewalDate = "2026-12-01" },
            new Customer { CustomerId = "C-001", RenewalDate = "2026-11-02" },
            new Customer { CustomerId = "C-002", RenewalDate = "2027-03-15" },
        };

        var due = RenewalWorkflow.DueBy(customers, new DateOnly(2026, 12, 31));

        Assert.Equal(new[] { "C-001", "C-003" }, due.Select(c => c.CustomerId));
    }

    [Fact]
    public void ConsentBreakdownCountsEachState()
    {
        var customers = new[]
        {
            new Customer { CustomerId = "C-001", ConsentStatus = "opt_in" },
            new Customer { CustomerId = "C-002", ConsentStatus = "opt_in" },
            new Customer { CustomerId = "C-003", ConsentStatus = "opt_out" },
        };

        var breakdown = RenewalWorkflow.ConsentBreakdown(customers);

        Assert.Equal(2, breakdown["opt_in"]);
        Assert.Equal(1, breakdown["opt_out"]);
    }
}
