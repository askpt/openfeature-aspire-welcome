using Aspire.Hosting.Foundry;
using Azure.Provisioning;
using Azure.Provisioning.CognitiveServices;
using Azure.Provisioning.Expressions;
using Azure.Provisioning.Resources;
using Azure.Provisioning.Roles;
using Azure.Provisioning.Storage;
using Scalar.Aspire;

var builder = DistributedApplication.CreateBuilder(args);

// Add Azure Container App Environment for publishing
var containerAppEnvironment = builder
    .AddAzureContainerAppEnvironment("cae");

// Microsoft Foundry provides the chat model: Foundry Local on the developer machine,
// a provisioned Azure AI Foundry account when published.
var foundry = builder.AddFoundry("foundry")
    .RunAsFoundryLocal();

// Foundry Local only serves on-device models, so the Phi-4 descriptor differs per mode
// even though both resolve to the same model family. Phi-4-mini keeps the chatbot responsive
// on developer machines without a dedicated GPU.
var chatModel = foundry.AddDeployment(
    "chat-model",
    builder.ExecutionContext.IsPublishMode ? FoundryModel.Microsoft.Phi4MiniInstruct : FoundryModel.Local.Phi4Mini);

var cache = builder.AddAzureManagedRedis("cache").RunAsContainer();

var postgres = builder.AddAzurePostgresFlexibleServer("postgres").RunAsContainer();
var database = postgres.AddDatabase("garage-db");

var apiService = builder.AddProject<Projects.Garage_ApiService>("apiservice")
    .WithReference(database)
    .WaitFor(database)
    .WithReference(cache)
    .WaitFor(cache)
    .PublishAsAzureContainerApp((infra, app) =>
    {
    })
    .WithHttpHealthCheck("/health");

var migrations = apiService.AddEFMigrations("api-migrations", "Garage.ApiModel.Data.GarageDbContext");

var webFrontend = builder.AddJavaScriptApp("web", "../Garage.Web/");

// Add Python chat service using Uvicorn (FastAPI/ASGI)
var chatService = builder.AddUvicornApp("chatservice", "../Garage.ChatService/", "main:app")
    .WithUv()
    .WithExternalHttpEndpoints()
    .WithReference(chatModel)
    .WaitFor(chatModel)
    .WithEnvironment("OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT", "true")
    .WithOtlpExporter()
    .WithHttpHealthCheck("/health")
    .PublishAsDockerFile();

if (builder.ExecutionContext.IsPublishMode)
{
    // Foundry Local publishes a ready-to-use OpenAI base URL, but Azure AI Foundry only exposes the
    // account root, so the OpenAI-compatible route has to be appended there.
    // Azure AI Foundry also has local auth disabled, so the chat service authenticates with its
    // managed identity instead of an API key.
    chatService = chatService
        .WithArgs("main:app", "--host", "0.0.0.0", "--port", "8000")
        .WithEnvironment("CHAT_MODEL_API_PATH", "openai/v1")
        .WithRoleAssignments(foundry, CognitiveServicesBuiltInRole.CognitiveServicesUser);
}

// Feature flags infrastructure
var flagd = builder.AddFlagd("flagd");

var flagsApi = builder.AddGoApp("flagsapi", "../Garage.FeatureFlags/")
    .WithHttpEndpoint(env: "PORT")
    .WithExternalHttpEndpoints()
    .PublishAsDockerFile();

if (!builder.ExecutionContext.IsPublishMode)
{
    // Add local Grafana provisioning path for dashboards
    var grafanaProvisioningPath = Path.Combine(builder.AppHostDirectory, "grafana", "provisioning", "dashboards");
    if (!Directory.Exists(grafanaProvisioningPath))
    {
        throw new DirectoryNotFoundException($"Grafana provisioning path not found: {grafanaProvisioningPath}");
    }

    // Add Grafana LGTM stack (Loki, Tempo, Prometheus, Pyroscope, Grafana)
    var lgtm = builder.AddContainer("lgtm", "grafana/otel-lgtm", "latest")
        .WithHttpEndpoint(port: 3000, targetPort: 3000, name: "grafana")
        .WithBindMount(grafanaProvisioningPath, "/otel-lgtm/grafana/conf/provisioning/dashboards", isReadOnly: true)
        .WithExternalHttpEndpoints();

    // Add collector for OpenTelemetry signals
    var collector = builder.AddOpenTelemetryCollector("opentelemetry-collector")
        .WithConfig("otel/config.yaml")
        .WithExternalHttpEndpoints()
        .WithAppForwarding()
        .WaitFor(lgtm);

    // Local development: flagd reads from host filesystem via bind mount
    var flagsPath = Path.Combine(builder.AppHostDirectory, "flags", "flagd.json");
    flagd.WithBindFileSync(Path.GetDirectoryName(flagsPath)!);

    flagd = flagd.WaitFor(collector);
    chatService = chatService.WaitFor(collector);
    apiService = apiService.WaitFor(collector);
    migrations = migrations.WaitFor(collector);

    flagsApi = flagsApi
        .WaitFor(collector)
        .WithEnvironment("FLAGS_FILE_PATH", flagsPath)
        .WaitFor(flagd);

    // Add API Reference
    var scalar = builder.AddScalarApiReference()
        .WithApiReference(apiService)
        .WaitFor(apiService);

    var tunnel = builder.AddDevTunnel("tunnel")
                    .WithReference(flagd)
                    .WithAnonymousAccess();

    // Browser telemetry is sent directly from the browser to the collector, so it
    // must target the collector's HTTP OTLP endpoint (port 4318) which has CORS
    // configured — browsers can't use gRPC. Setting the protocol to "http" makes
    // WithAppForwarding route to the collector's "http" endpoint instead of "grpc".
    webFrontend = webFrontend
        .WithBrowserLogs()
        .WithOtlpExporter()
        .WithEnvironment("OTEL_EXPORTER_OTLP_PROTOCOL", "http")
        .WaitFor(collector);

    var k6 = builder.AddK6("k6")
                .WithBindMount("k6", "/scripts", isReadOnly: true)
                .WithScript("/scripts/main.js", virtualUsers: 8, duration: "1h")
                .WithReference(apiService)
                .WaitFor(apiService)
                .WithReference(webFrontend)
                .WaitFor(webFrontend)
                .WithEnvironment("K6_WEB_DASHBOARD", "true")
                .WithHttpEndpoint(targetPort: 5665, name: "k6-dashboard")
                .WithUrlForEndpoint("k6-dashboard", url => url.DisplayText = "K6 Dashboard")
                .WithK6OtlpEnvironment();

    var k6_error = builder.AddK6("k6-error")
                .WithBindMount("k6", "/scripts", isReadOnly: true)
                .WithScript("/scripts/test_error.js", virtualUsers: 8, duration: "1h")
                .WithReference(apiService)
                .WaitFor(apiService)
                .WithReference(webFrontend)
                .WaitFor(webFrontend)
                .WithEnvironment("K6_WEB_DASHBOARD", "true")
                .WithHttpEndpoint(targetPort: 5665, name: "k6-dashboard")
                .WithUrlForEndpoint("k6-dashboard", url => url.DisplayText = "K6 Dashboard")
                .WithK6OtlpEnvironment();
}
else
{
    // Azure deployment: flagd reads from Azure Blob Storage (azblob:// sync),
    // flagsapi reads/writes via gocloud.dev blob SDK — no shared volume needed
    var flagsStorage = builder.AddAzureStorage("flags-storage");
    var flagsBlobs = flagsStorage.AddBlobs("flags-blobs");
    var defaultFlagsBase64 = Convert.ToBase64String(
        File.ReadAllBytes(Path.Combine(builder.AppHostDirectory, "flags", "flagd.json")));

    ConfigureAzureFlagsInfrastructure(flagsStorage, defaultFlagsBase64);

    var accountName = flagsStorage.GetOutput("accountName");
    var seedScriptId = flagsStorage.GetOutput("seedScriptId");

    flagsApi = flagsApi
        .WithReference(flagsBlobs)
        .WithEnvironment("OTEL_EXPORTER_OTLP_PROTOCOL", "http/protobuf")
        .WithEnvironment("AZURE_STORAGE_ACCOUNT", accountName)
        .WithEnvironment("FLAGS_BLOB_CONTAINER", "flags")
        .WithEnvironment("FLAGS_BLOB_NAME", "flagd.json");

    flagd = flagd
        .WithEnvironment("FLAGS_SEED_SCRIPT_ID", seedScriptId)
        .WithReference(flagsBlobs)
        .WithEnvironment("AZURE_STORAGE_ACCOUNT", accountName)
        .WithArgs("--uri", "azblob://flags/flagd.json");
}

// Wire OFREP endpoint to all services
var ofrepEndpoint = flagd.GetEndpoint("ofrep");

apiService = apiService
    .WaitFor(flagd)
    .WithEnvironment("OFREP_ENDPOINT", ofrepEndpoint);

flagsApi = flagsApi
    .WithEnvironment("OFREP_ENDPOINT", ofrepEndpoint);

chatService = chatService
    .WaitFor(flagd)
    .WithEnvironment("OFREP_ENDPOINT", ofrepEndpoint);

webFrontend
    .WithReference(apiService)
    .WaitFor(apiService)
    .WaitFor(flagd)
    .WithReference(flagsApi)
    .WaitFor(flagsApi)
    .WithReference(chatService)
    .WaitFor(chatService)
    .WithEnvironment("OFREP_ENDPOINT", ofrepEndpoint)
    .WithEnvironment("BROWSER", "none")
    .WithHttpEndpoint(env: "VITE_PORT")
    .WithExternalHttpEndpoints()
    .PublishAsDockerFile();



builder.Build().Run();

// Provision Azure Blob Storage for feature flags (blob container + seed script)
static void ConfigureAzureFlagsInfrastructure(
    IResourceBuilder<Aspire.Hosting.Azure.AzureStorageResource> flagsStorage,
    string defaultFlagsBase64)
{
    flagsStorage.ConfigureInfrastructure(infra =>
    {
        var account = infra.GetProvisionableResources()
            .OfType<StorageAccount>()
            .Single();

        var blobService = infra.GetProvisionableResources()
            .OfType<BlobService>()
            .SingleOrDefault();

        if (blobService is null)
        {
            blobService = new BlobService("default") { Parent = account };
            infra.Add(blobService);
        }

        var flagsContainer = new BlobContainer("flags") { Parent = blobService, Name = "flags" };
        infra.Add(flagsContainer);

        var seedScriptIdentity = new UserAssignedIdentity("seedScriptIdentity")
        {
            Name = BicepFunction.Interpolate($"seed-flags-mi-{BicepFunction.Take(BicepFunction.GetUniqueString(BicepFunction.GetResourceGroup().Id), 8)}"),
            Location = BicepFunction.GetResourceGroup().Location
        };
        infra.Add(seedScriptIdentity);

        var seedScriptBlobRoleAssignment = account.CreateRoleAssignment(StorageBuiltInRole.StorageBlobDataContributor, seedScriptIdentity);
        seedScriptBlobRoleAssignment.Name = BicepFunction.CreateGuid(account.Id, "seedflagsblobrole");
        infra.Add(seedScriptBlobRoleAssignment);

        // Seed flags/flagd.json during infrastructure provisioning so flagd can start on first deploy.
        var seedFlagsScript = new AzureCliScript("seedFlags")
        {
            Name = BicepFunction.Interpolate($"seed-flags-{BicepFunction.Take(BicepFunction.GetUniqueString(BicepFunction.GetResourceGroup().Id, BicepFunction.GetDeployment().Name), 8)}"),
            Location = BicepFunction.GetResourceGroup().Location,
            Identity = new ArmDeploymentScriptManagedIdentity
            {
                IdentityType = ArmDeploymentScriptManagedIdentityType.UserAssigned,
                UserAssignedIdentities =
                {
                    ["${seedScriptIdentity.id}"] = new UserAssignedIdentityDetails()
                }
            },
            AzCliVersion = "2.60.0",
            CleanupPreference = ScriptCleanupOptions.Always,
            ForceUpdateTag = BicepFunction.GetDeployment().Name,
            RetentionInterval = TimeSpan.FromDays(1),
            Timeout = TimeSpan.FromMinutes(10),
            ScriptContent = """
                set -euo pipefail

                az login --identity --username "$SEED_IDENTITY_CLIENT_ID" --allow-no-subscriptions >/dev/null
                BLOB_EXISTS=$(az storage blob exists --account-name "$AZURE_STORAGE_ACCOUNT" --container-name "$FLAGS_CONTAINER" --name "$FLAGS_BLOB_NAME" --auth-mode login --query exists -o tsv)

                if [ "$BLOB_EXISTS" != "true" ]; then
                                    echo "$FLAGS_FILE_BASE64" | base64 -d > /tmp/flagd.json
                  az storage blob upload --account-name "$AZURE_STORAGE_ACCOUNT" --container-name "$FLAGS_CONTAINER" --name "$FLAGS_BLOB_NAME" --file /tmp/flagd.json --overwrite false --content-type application/json --auth-mode login
                fi
                """
        };

        seedFlagsScript.EnvironmentVariables.Add(new ScriptEnvironmentVariable
        {
            Name = "AZURE_STORAGE_ACCOUNT",
            Value = account.Name
        });
        seedFlagsScript.EnvironmentVariables.Add(new ScriptEnvironmentVariable
        {
            Name = "SEED_IDENTITY_CLIENT_ID",
            Value = seedScriptIdentity.ClientId
        });
        seedFlagsScript.EnvironmentVariables.Add(new ScriptEnvironmentVariable
        {
            Name = "FLAGS_CONTAINER",
            Value = "flags"
        });
        seedFlagsScript.EnvironmentVariables.Add(new ScriptEnvironmentVariable
        {
            Name = "FLAGS_BLOB_NAME",
            Value = "flagd.json"
        });
        seedFlagsScript.EnvironmentVariables.Add(new ScriptEnvironmentVariable
        {
            Name = "FLAGS_FILE_BASE64",
            Value = defaultFlagsBase64
        });

        infra.Add(seedFlagsScript);

        infra.Add(new ProvisioningOutput("accountName", typeof(string))
        {
            Value = account.Name
        });
        infra.Add(new ProvisioningOutput("seedScriptId", typeof(string))
        {
            Value = seedFlagsScript.Id
        });
    });
}
