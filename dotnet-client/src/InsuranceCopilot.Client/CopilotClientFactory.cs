using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Options;

namespace InsuranceCopilot.Client;

/// <summary>Which implementation of <see cref="ICopilotClient"/> to resolve.</summary>
public enum CopilotProvider
{
    /// <summary>Talk to the Python FastAPI service over HTTP.</summary>
    Http,

    /// <summary>Use the in-memory stand-in: no network, same policy rules.</summary>
    Mock,
}

public sealed class CopilotOptions
{
    public const string SectionName = "Copilot";

    public CopilotProvider Provider { get; set; } = CopilotProvider.Http;

    public string BaseUrl { get; set; } = "http://127.0.0.1:8000";

    public int TimeoutSeconds { get; set; } = 30;
}

/// <summary>
/// Factory method: the caller asks for an <see cref="ICopilotClient"/> and the configured
/// provider decides which concrete type it gets. Adding a third provider (an Azure-hosted
/// endpoint, say) means adding a case here, not changing any caller.
/// </summary>
public interface ICopilotClientFactory
{
    ICopilotClient Create(CopilotProvider? provider = null);
}

public sealed class CopilotClientFactory : ICopilotClientFactory
{
    private readonly IHttpClientFactory _httpClientFactory;
    private readonly CopilotOptions _options;

    public CopilotClientFactory(IHttpClientFactory httpClientFactory, IOptions<CopilotOptions> options)
    {
        _httpClientFactory = httpClientFactory;
        _options = options.Value;
    }

    public ICopilotClient Create(CopilotProvider? provider = null) => (provider ?? _options.Provider) switch
    {
        CopilotProvider.Mock => new MockCopilotClient(),
        CopilotProvider.Http => new CopilotClient(_httpClientFactory.CreateClient(ServiceCollectionExtensions.HttpClientName)),
        var unknown => throw new ArgumentOutOfRangeException(nameof(provider), unknown, "Unknown copilot provider."),
    };
}

public static class ServiceCollectionExtensions
{
    public const string HttpClientName = "copilot";

    /// <summary>
    /// Registers the copilot client and its dependencies.
    ///
    /// Lifetimes, chosen deliberately:
    ///   - the typed HttpClient is managed by IHttpClientFactory, which pools and rotates handlers;
    ///   - the factory is singleton, because it holds only configuration;
    ///   - ICopilotClient is transient, so a scope that swaps provider mid-run gets a fresh client.
    /// </summary>
    public static IServiceCollection AddCopilotClient(
        this IServiceCollection services,
        Action<CopilotOptions>? configure = null)
    {
        var options = new CopilotOptions();
        configure?.Invoke(options);

        services.Configure<CopilotOptions>(opts =>
        {
            opts.Provider = options.Provider;
            opts.BaseUrl = options.BaseUrl;
            opts.TimeoutSeconds = options.TimeoutSeconds;
        });

        services.AddHttpClient(HttpClientName, http =>
        {
            http.BaseAddress = new Uri(options.BaseUrl);
            http.Timeout = TimeSpan.FromSeconds(options.TimeoutSeconds);
        });

        services.AddSingleton<ICopilotClientFactory, CopilotClientFactory>();
        services.AddTransient(sp => sp.GetRequiredService<ICopilotClientFactory>().Create());

        return services;
    }
}
