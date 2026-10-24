using InsuranceCopilot.Client;
using Microsoft.Extensions.DependencyInjection;
using Xunit;

namespace InsuranceCopilot.Client.Tests;

public class DependencyInjectionTests
{
    [Fact]
    public void MockProviderResolvesTheInMemoryClient()
    {
        using var provider = new ServiceCollection()
            .AddCopilotClient(o => o.Provider = CopilotProvider.Mock)
            .BuildServiceProvider();

        Assert.IsType<MockCopilotClient>(provider.GetRequiredService<ICopilotClient>());
    }

    [Fact]
    public void HttpProviderResolvesTheHttpClient()
    {
        using var provider = new ServiceCollection()
            .AddCopilotClient(o =>
            {
                o.Provider = CopilotProvider.Http;
                o.BaseUrl = "http://localhost:8000";
            })
            .BuildServiceProvider();

        Assert.IsType<CopilotClient>(provider.GetRequiredService<ICopilotClient>());
    }

    [Fact]
    public void FactoryCanOverrideTheConfiguredProvider()
    {
        using var provider = new ServiceCollection()
            .AddCopilotClient(o => o.Provider = CopilotProvider.Http)
            .BuildServiceProvider();

        var factory = provider.GetRequiredService<ICopilotClientFactory>();

        Assert.IsType<MockCopilotClient>(factory.Create(CopilotProvider.Mock));
    }

    [Fact]
    public void FactoryIsSingletonAndClientIsTransient()
    {
        using var provider = new ServiceCollection()
            .AddCopilotClient(o => o.Provider = CopilotProvider.Mock)
            .BuildServiceProvider();

        Assert.Same(
            provider.GetRequiredService<ICopilotClientFactory>(),
            provider.GetRequiredService<ICopilotClientFactory>());

        Assert.NotSame(
            provider.GetRequiredService<ICopilotClient>(),
            provider.GetRequiredService<ICopilotClient>());
    }
}
