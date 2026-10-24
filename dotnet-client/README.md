# .NET 8 client

A typed async client for the copilot API, showing dependency injection, the factory pattern,
`async`/`await`, LINQ and `System.Text.Json` serialisation.

## Run

```bash
# against the Python API (start it first: uvicorn copilot.api:app)
dotnet run --project src/InsuranceCopilot.Client

# without the API running
dotnet run --project src/InsuranceCopilot.Client -- --mock

# a specific synthetic customer
dotnet run --project src/InsuranceCopilot.Client -- --mock C-999
```

## Test

```bash
dotnet test
```

## Design

| Piece | Why |
| --- | --- |
| `ICopilotClient` | One interface, two implementations, so callers and tests swap providers freely. |
| `CopilotClient` | HTTP implementation. `HttpClient` is injected from `IHttpClientFactory`, not constructed. |
| `MockCopilotClient` | In-memory stand-in that enforces the **same** approval and consent rules, so a test cannot pass for a reason the real service would reject. |
| `CopilotClientFactory` | Factory method: configuration decides which concrete client is returned. Adding an Azure-hosted provider means one new case, not changes to callers. |
| `RenewalWorkflow` | The agent flow, written once against the interface. `approve` is the human gate: nothing sends without it. |

### Lifetimes

- The named `HttpClient` is managed by `IHttpClientFactory`, which pools and rotates handlers.
- `ICopilotClientFactory` is **singleton**: it holds only configuration.
- `ICopilotClient` is **transient**, so a scope that swaps provider mid-run gets a fresh client.

## Safety

The client cannot bypass the API's rules. A send without approval, without an agent ID, or for a
customer who is not opted in raises `CopilotPolicyException`. There are tests for each case.
