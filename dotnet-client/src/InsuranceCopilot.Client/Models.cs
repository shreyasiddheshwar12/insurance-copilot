using System.Text.Json.Serialization;

namespace InsuranceCopilot.Client;

/// <summary>A synthetic customer record returned by the copilot API.</summary>
public sealed record Customer
{
    [JsonPropertyName("customer_id")]
    public required string CustomerId { get; init; }

    [JsonPropertyName("city")]
    public string City { get; init; } = "";

    [JsonPropertyName("renewal_date")]
    public string RenewalDate { get; init; } = "";

    [JsonPropertyName("synthetic_segment")]
    public string SyntheticSegment { get; init; } = "";

    [JsonPropertyName("consent_status")]
    public string ConsentStatus { get; init; } = "";

    [JsonPropertyName("fictional_plan_id")]
    public string? FictionalPlanId { get; init; }

    /// <summary>True only when the customer has explicitly opted in.</summary>
    [JsonIgnore]
    public bool HasConsent => ConsentStatus == "opt_in";
}

/// <summary>The copilot's answer. Asking never sends anything.</summary>
public sealed record AskResult
{
    [JsonPropertyName("intents")]
    public IReadOnlyList<string> Intents { get; init; } = Array.Empty<string>();

    [JsonPropertyName("answer_parts")]
    public IReadOnlyList<string> AnswerParts { get; init; } = Array.Empty<string>();

    [JsonPropertyName("citations")]
    public IReadOnlyList<string> Citations { get; init; } = Array.Empty<string>();

    [JsonPropertyName("warnings")]
    public IReadOnlyList<string> Warnings { get; init; } = Array.Empty<string>();

    [JsonPropertyName("missing_inputs")]
    public IReadOnlyList<string> MissingInputs { get; init; } = Array.Empty<string>();

    [JsonPropertyName("escalated")]
    public bool Escalated { get; init; }

    [JsonPropertyName("draft_id")]
    public string? DraftId { get; init; }

    [JsonPropertyName("safety_flags")]
    public IReadOnlyList<string> SafetyFlags { get; init; } = Array.Empty<string>();

    [JsonPropertyName("predicted_intent")]
    public string? PredictedIntent { get; init; }

    [JsonPropertyName("intent_confidence")]
    public double? IntentConfidence { get; init; }

    /// <summary>True when the copilot produced no claim without a source to back it.</summary>
    [JsonIgnore]
    public bool IsGrounded => AnswerParts.Count == 0 || Citations.Count > 0 || Escalated;
}

/// <summary>A reminder draft. It is never sent without approval and recorded consent.</summary>
public sealed record Draft
{
    [JsonPropertyName("draft_id")]
    public required string DraftId { get; init; }

    [JsonPropertyName("customer_id")]
    public string CustomerId { get; init; } = "";

    [JsonPropertyName("template_id")]
    public string TemplateId { get; init; } = "";

    [JsonPropertyName("text")]
    public string Text { get; init; } = "";

    [JsonPropertyName("citations")]
    public IReadOnlyList<string> Citations { get; init; } = Array.Empty<string>();

    [JsonPropertyName("status")]
    public string Status { get; init; } = "";

    [JsonPropertyName("approved_by")]
    public string? ApprovedBy { get; init; }

    [JsonPropertyName("simulated_sent_at")]
    public string? SimulatedSentAt { get; init; }

    [JsonIgnore]
    public bool AwaitingApproval => Status == "pending_approval";
}

/// <summary>Thrown when the API refuses an action, for example a send without approval.</summary>
public sealed class CopilotPolicyException : Exception
{
    public CopilotPolicyException(string message, int statusCode) : base(message)
        => StatusCode = statusCode;

    public int StatusCode { get; }
}
