# GitHub Copilot Instructions for OpenFeature Aspire Sample

## Project Overview

This is an OpenFeature .NET OFREP Demo application - a Le Mans Winners Management System that demonstrates feature flag capabilities using OpenFeature and the Remote Evaluation Protocol (OFREP) in a polyglot environment with .NET, Python, Go, and React frontend.
This repository is set up to use Aspire. Aspire is an orchestrator for the entire application and will take care of configuring dependencies, building, and running the application. The resources that make up the application are defined in `apphost` including application code and external dependencies.

### Technology Stack

- **.NET**: 10.0 (latest version)
- **Python**: 3.14+ (for Chat Service with Microsoft Foundry)
- **Go**: 1.25 (for Feature Flags API)
- **Frontend**: React 19.2 with TypeScript, Vite 7.2
- **Backend**: ASP.NET Core 10.0 with Entity Framework Core
- **Orchestration**: .NET Aspire 13.0
- **Feature Flags**: OpenFeature with OFREP and flagd provider
- **AI/Chat**: Microsoft Foundry (Phi-4-mini) with GitHub Repository Prompts
- **Database**: PostgreSQL with Entity Framework Core
- **Caching**: Redis via StackExchange.Redis
- **Telemetry**: OpenTelemetry integration (traces, metrics, logs)
- **Mapping**: Riok.Mapperly for object mapping

### Project Structure

```
/
├── src/
│   ├── Garage.ApiDatabaseSeeder/  # Database initialization
│   ├── Garage.ApiService/      # REST API service
│   ├── Garage.AppHost/         # .NET Aspire orchestration
│   ├── Garage.ChatService/     # Python FastAPI chatbot service
│   │   ├── main.py             # FastAPI application
│   │   ├── prompt_loader.py    # GitHub Repository Prompts loader
│   │   ├── pyproject.toml      # Python dependencies (uv-managed)
│   │   └── prompts/            # .prompt.yml files
│   ├── Garage.FeatureFlags/    # Go API for feature flag management
│   ├── Garage.ServiceDefaults/ # Shared services & feature flags
│   ├── Garage.Shared/          # Common models and DTOs
│   └── Garage.Web/             # React + Vite frontend
├── .github/                    # CI/CD workflows
├── Directory.Build.props       # Common .NET build properties
└── Garage.slnx                 # Solution file
```

## Build and Development Commands

### .NET Backend

```bash
# Restore dependencies
dotnet restore

# Build the solution
dotnet build

# Build in Release mode
dotnet build --configuration Release

# Run the application (from AppHost)
cd src/Garage.AppHost
dotnet run

# Format code
dotnet format

# Verify formatting
dotnet format --verify-no-changes
```

### React Frontend

```bash
cd src/Garage.Web

# Install dependencies
npm install

# Development server
npm run dev

# Build for production
npm run build

# Lint code
npm run lint

# Preview production build
npm run preview
```

### Go Feature Flags API

```bash
cd src/Garage.FeatureFlags

# Download dependencies
go mod download

# Build the application
go build -o flagsapi .

# Run the application
go run .

# Format code
go fmt ./...

# Run linter (requires golangci-lint)
golangci-lint run
```

### Python Chat Service

```bash
cd src/Garage.ChatService

# Create/update virtual environment and install dependencies
uv sync --group dev

# Run the application (development)
uv run uvicorn main:app --reload --port 8080

# Format code
uvx black .

# Type checking
uvx mypy .
```

## Coding Standards and Conventions

### .NET Code

- **Language Version**: Latest C# features enabled
- **Nullable Reference Types**: Enabled throughout the project
- **Warnings as Errors**: All warnings are treated as errors (`TreatWarningsAsErrors=true`)
- **Implicit Usings**: Enabled for cleaner code
- **Formatting**: Follow `dotnet format` conventions as defined in `.editorconfig`

### TypeScript/React Code

- **Linting**: ESLint with TypeScript parser
- **Type Safety**: TypeScript strict mode (~5.9.3)
- **React Version**: 19.2 with hooks
- **Style**: Follow ESLint rules in the configuration
- **Module System**: ES modules

### Go Code

- **Go Version**: 1.25 or later
- **Formatting**: Use `go fmt` for code formatting
- **Error Handling**: Follow Go idioms for error handling
- **Telemetry**: OpenTelemetry integration for tracing, metrics, and logging
- **HTTP Framework**: Standard library `net/http` with `otelhttp` instrumentation
- **Feature Flags**: OpenFeature Go SDK with OFREP provider

### Python Code

- **Python Version**: 3.14 or later
- **Framework**: FastAPI with Uvicorn (ASGI)
- **Formatting**: Use `black` for code formatting
- **Type Hints**: Use type hints throughout
- **Telemetry**: OpenTelemetry integration (traces, metrics, logs via OTLP gRPC)
- **Feature Flags**: OpenFeature Python SDK with OFREP provider
- **Prompts**: GitHub Repository Prompts format (`.prompt.yml` files)

## Important Patterns and Practices

### Feature Flags

When working with feature flags:
- Use OpenFeature SDK for .NET, Python, Go, and React
- Feature flag keys use kebab-case (e.g., `enable-database-winners`)
- Boolean flags for toggle features
- Integer flags for numeric values
- String flags for selecting variants (e.g., prompt files)
- Targeting rules supported via flagd

Example feature flags in use:
- `enable-database-winners`: Toggle between database and JSON data sources
- `winners-count`: Control number of items displayed
- `enable-stats-header`: Show/hide statistics header
- `enable-tabs`: Enable tabbed interface
- `enable-preview-mode`: Comma-separated list of flags that can be dynamically updated
- `enable-chatbot`: Show/hide AI chatbot (with user targeting)
- `prompt-file`: Select chatbot prompt style (expert, casual, brief, unreliable)

### GitHub Repository Prompts

The chatbot uses GitHub Repository Prompts format for dynamic prompt selection:

```yaml
# prompts/expert.prompt.yml
name: Le Mans Expert
description: A knowledgeable Le Mans racing historian
model: microsoft/phi-4-mini
modelParameters:
  temperature: 0.7
messages:
  - role: system
    content: |
      You are a Le Mans 24 Hours racing expert...
  - role: user
    content: "{{message}}"
```

Available prompt styles:
- `expert`: Detailed Le Mans historian with comprehensive knowledge
- `casual`: Friendly enthusiast for casual conversation
- `brief`: Quick facts with concise responses
- `unreliable`: Confidently incorrect (for A/B testing demos)

### Service Configuration

- Service defaults are in `Garage.ServiceDefaults` for shared configuration
- Use .NET Aspire for service orchestration and discovery
- All services include OpenTelemetry instrumentation
- Python services use `AddUvicornApp` with `.WithUv()` for package management

### Database Access

- Use Entity Framework Core with PostgreSQL provider
- Database context should be registered via Aspire integration
- Migrations are managed through EF Core

## Testing

Currently, there are no test projects in the solution. When adding tests:
- Follow xUnit or NUnit conventions
- Create test projects with `*.Tests.csproj` naming
- Include both unit tests and integration tests where appropriate
- For React components, consider adding Vitest or Jest
- For Python, use pytest

## CI/CD

### GitHub Actions Workflows

1. **CI Build** (`.github/workflows/ci.yml`)
   - Runs on push to main and all PRs
   - Builds with `dotnet build --configuration Release`
   - Tests are commented out (add when test projects exist)

2. **Format Check** (`.github/workflows/format.yml`)
   - Runs on push to main and PRs to main
   - Verifies code formatting with `dotnet format --verify-no-changes`

## Dependencies and Security

- Use Dependabot for dependency updates (configured in `.github/dependabot.yml`)
- Dependabot monitors: NuGet, npm, uv, Go modules, GitHub Actions, Docker
- Keep .NET SDK at version 10.0.100 or later (see `global.json`)
- Review and update NuGet, npm, and uv-managed Python packages regularly
- Follow security best practices for feature flag configuration
- Install Foundry Local so the chat model can run on-device during development

## Documentation

- Main README in root provides project overview and quick start
- Component-specific README in `src/Garage.Web/README.md`
- Update documentation when adding new features or changing architecture
- Include inline code comments for complex business logic

## Common Tasks

### Adding a New Feature Flag

1. Define the flag in flagd configuration (`src/Garage.AppHost/flags/flagd.json`)
2. Add flag evaluation in service defaults or directly in service code
3. Use in .NET: `await _featureClient.GetBooleanValueAsync("flag-name", false)`
4. Use in React: `const flagValue = useBooleanFlagValue('flag-name', false)`
5. Use in Python: `client.get_boolean_value("flag-name", False, eval_context)`
6. Use in Go: `client.BooleanValue(ctx, "flag-name", false, evalCtx)`

### Adding a New Chatbot Prompt

1. Create a new `.prompt.yml` file in `src/Garage.ChatService/prompts/`
2. Follow the GitHub Repository Prompts format
3. Add the variant to `prompt-file` flag in `flagd.json`
4. Configure targeting rules if needed for A/B testing

### Adding a New API Endpoint

1. Add to `Garage.ApiService` controllers
2. Add DTO if needed in `Garage.Shared`
3. Update OpenAPI documentation
4. Add caching if appropriate

### Database Schema Changes

1. Update Entity Framework models
2. Create migration: `dotnet ef migrations add MigrationName`
3. Update database seeder if needed
4. Test migration rollback

## Notes for Copilot

- This is a demonstration/sample application showcasing OpenFeature capabilities
- Code quality is important - maintain clean, maintainable code
- Feature flags are central to this project - understand OFREP concepts
- The application uses .NET Aspire for cloud-ready development
- All services (backend, frontend, Python, Go) use OpenFeature for consistent feature flag experience
- The Go Feature Flags API (`Garage.FeatureFlags`) provides dynamic flag targeting management
  - Exposes REST endpoints for getting and updating flag targeting rules
  - Uses OpenFeature Go SDK with OFREP provider for flag evaluation
  - Includes full OpenTelemetry instrumentation (traces, metrics, logs)
  - Reads/writes to the flagd.json configuration file
- The Python Chat Service (`Garage.ChatService`) provides AI-powered chatbot
  - Uses FastAPI with Uvicorn (ASGI)
  - Integrates with Microsoft Foundry (Phi-4-mini) for AI responses via the OpenAI-compatible API
  - Foundry Local in run mode (`CHAT_MODEL_KEY` is injected), Azure AI Foundry in publish mode (Entra ID via `DefaultAzureCredential`)
  - Reads `CHAT_MODEL_URI`, `CHAT_MODEL_API_PATH`, `CHAT_MODEL_KEY`, and `CHAT_MODEL_MODELNAME` from Aspire
  - Uses OpenFeature OFREP provider for feature flags
  - Supports GitHub Repository Prompts (`.prompt.yml`) for dynamic prompt selection
  - Includes full OpenTelemetry instrumentation (traces, metrics, logs via OTLP gRPC)
  - Custom metrics: `chat_requests_total` counter, `chat_request_duration_seconds` histogram

## General recommendations for working with Aspire
1. Before making any changes always run the apphost using `aspire run` and inspect the state of resources to make sure you are building from a known state.
2. Changes to the _apphost.cs_ file will require a restart of the application to take effect.
3. Make changes incrementally and run the aspire application using the `aspire run` command to validate changes.
4. Use the Aspire MCP tools to check the status of resources and debug issues.

## Running the application
To run the application run the following command:

```
aspire run
```

If there is already an instance of the application running it will prompt to stop the existing instance. You only need to restart the application if code in `apphost.cs` is changed, but if you experience problems it can be useful to reset everything to the starting state.

## Checking resources
To check the status of resources defined in the app model use the _list resources_ tool. This will show you the current state of each resource and if there are any issues. If a resource is not running as expected you can use the _execute resource command_ tool to restart it or perform other actions.

## Listing integrations
IMPORTANT! When a user asks you to add a resource to the app model you should first use the _list integrations_ tool to get a list of the current versions of all the available integrations. You should try to use the version of the integration which aligns with the version of the Aspire.AppHost.Sdk. Some integration versions may have a preview suffix. Once you have identified the correct integration you should always use the _get integration docs_ tool to fetch the latest documentation for the integration and follow the links to get additional guidance.

## Debugging issues
IMPORTANT! Aspire is designed to capture rich logs and telemetry for all resources defined in the app model. Use the following diagnostic tools when debugging issues with the application before making changes to make sure you are focusing on the right things.

1. _list structured logs_; use this tool to get details about structured logs.
2. _list console logs_; use this tool to get details about console logs.
3. _list traces_; use this tool to get details about traces.
4. _list trace structured logs_; use this tool to get logs related to a trace

## Other Aspire MCP tools

1. _select apphost_; use this tool if working with multiple app hosts within a workspace.
2. _list apphosts_; use this tool to get details about active app hosts.

## Playwright MCP server

The playwright MCP server has also been configured in this repository and you should use it to perform functional investigations of the resources defined in the app model as you work on the codebase. To get endpoints that can be used for navigation using the playwright MCP server use the list resources tool.

## Updating the app host
The user may request that you update the Aspire apphost. You can do this using the `aspire update` command. This will update the apphost to the latest version and some of the Aspire specific packages in referenced projects, however you may need to manually update other packages in the solution to ensure compatibility. You can consider using the `dotnet-outdated` with the users consent. To install the `dotnet-outdated` tool use the following command:

```
dotnet tool install --global dotnet-outdated-tool
```

## Persistent containers
IMPORTANT! Consider avoiding persistent containers early during development to avoid creating state management issues when restarting the app.

## Aspire workload
IMPORTANT! The aspire workload is obsolete. You should never attempt to install or use the Aspire workload.

## Official documentation
IMPORTANT! Always prefer official documentation when available. The following sites contain the official documentation for Aspire and related components

1. https://aspire.dev
2. https://learn.microsoft.com/dotnet/aspire
3. https://nuget.org (for specific integration package details)
