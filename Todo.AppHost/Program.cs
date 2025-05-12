var builder = DistributedApplication.CreateBuilder(args);

var redis = builder.AddRedis("cache");

// Access configuration values
var config = builder.Configuration.GetSection("flagd");
var source = config["Source"];
ArgumentException.ThrowIfNullOrWhiteSpace(source);

var flagd = builder.AddContainer("flagd", "ghcr.io/open-feature/flagd:latest")
    .WithBindMount(source, "/flags")
    .WithArgs("start", "--uri", "file:./flags/flagd.json")
    .WithEndpoint(8013, 8013);

var apiService = builder.AddProject<Projects.Todo_ApiService>("apiservice")
    .WithReference(redis)
    .WaitFor(redis)
    .WaitFor(flagd)
    .WithHttpsHealthCheck("/health");

builder.AddProject<Projects.Todo_Web>("webfrontend")
    .WithExternalHttpEndpoints()
    .WithReference(redis)
    .WaitFor(redis)
    .WaitFor(flagd)
    .WithHttpsHealthCheck("/health")
    .WithReference(apiService)
    .WaitFor(apiService);

builder.Build().Run();
