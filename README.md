# OpenFeature .NET OFREP Demo: Le Mans Winners Management System

[![.NET 10.0](https://img.shields.io/badge/.NET-10.0-512BD4?logo=dotnet)](https://dotnet.microsoft.com/)
[![Python 3.14](https://img.shields.io/badge/Python-3.14-3776AB?logo=python)](https://python.org/)
[![Go 1.25](https://img.shields.io/badge/Go-1.25-00ADD8?logo=go)](https://go.dev/)
[![Aspire 13.2](https://img.shields.io/badge/Aspire-13.2-purple)](https://learn.microsoft.com/en-us/dotnet/aspire/)
[![OpenFeature](https://img.shields.io/badge/OpenFeature-Ready-green)](https://openfeature.dev/)
[![OFREP](https://img.shields.io/badge/OFREP-Enabled-blue)](https://openfeature.dev/specification/ofrep)

A demonstration application showcasing **OpenFeature Remote Evaluation Protocol (OFREP)** capabilities in a polyglot environment with .NET, Python, Go, and React. This application manages a collection of Le Mans winner cars and includes an AI-powered chatbot.

## What This Demonstrates

This demo showcases how to implement feature flags using **OpenFeature** and the **OFREP (OpenFeature Remote Evaluation Protocol)** in a full-stack polyglot application. Key features include:

- **OFREP Integration**: Remote feature flag evaluation using the standardized protocol across .NET, Python, and Go
- **OpenFeature SDK**: Industry-standard feature flagging for .NET backend, Python service, and React frontend
- **flagd Provider**: Using flagd as the feature flag evaluation engine with OFREP
- **Dynamic Configuration**: Real-time feature flag updates without redeployment
- **Full-Stack Implementation**: Feature flags working seamlessly across React UI, .NET API, and Python services
- **Kill Switches**: Safely toggle features in production environments
- **Microsoft Foundry Integration**: AI-powered chatbot using Phi-4-mini, served by Foundry Local during development and Azure AI Foundry when deployed
- **GitHub Repository Prompts**: Dynamic prompt selection using `.prompt.yml` files

## Architecture

### Components

- **Garage.Web**: React + Vite frontend for managing car collections with floating chatbot UI
- **Garage.ApiService**: REST API for car data with Entity Framework Core
- **Garage.ApiModel**: Data model library containing the EF Core DbContext and entity definitions
- **Garage.ApiDatabaseSeeder**: Database migration and seeding service
- **Garage.ChatService**: Python FastAPI service for AI chatbot using Microsoft Foundry
- **Garage.FeatureFlags**: Go API for managing feature flag targeting rules
- **Garage.ServiceDefaults**: Shared services including OpenFeature, OpenTelemetry, and resilience configuration
- **Garage.Shared**: Common models, DTOs, and seed data
- **Garage.AppHost**: .NET Aspire orchestration, service discovery, and Azure deployment configuration

### Infrastructure

- **PostgreSQL**: Database for storing car collection data
- **Redis**: Caching layer for improved performance
- **flagd**: OpenFeature-compliant feature flag evaluation engine
- **Microsoft Foundry**: AI model provider for chatbot functionality (Foundry Local when running, Azure AI Foundry when published)
- **Dev Tunnels**: Secure tunneling for external access to flagd during development

## Telemetry Support

This application includes comprehensive telemetry support through .NET Aspire:

- **Distributed Tracing**: Track requests across all services (.NET, Python, Go)
- **Metrics Collection**: Monitor application performance, feature flag usage, and chat request counts
- **Structured Logging**: Centralized log aggregation with trace correlation

> **Note**: All services export telemetry via OTLP to the Aspire dashboard.

## Feature Flags Included

The demo demonstrates these feature flags:

| Flag                       | Type     | Purpose                                   | Default       |
| -------------------------- | -------- | ----------------------------------------- | ------------- |
| `enable-database-winners`  | `bool`   | Toggle data source (DB vs JSON)           | `true`        |
| `winners-count`            | `int`    | Control number of winners shown           | `100`         |
| `enable-stats-header`      | `bool`   | Show/hide statistics header               | `true`        |
| `enable-tabs`              | `bool`   | Enable tabbed interface (with targeting)  | `false`       |
| `enable-preview-mode`      | `string` | Comma-separated list of editable flags    | `""`          |
| `enable-chatbot`           | `bool`   | Show/hide AI chatbot (with targeting)     | `false`       |
| `prompt-file`              | `string` | Select chatbot prompt style               | `"expert"`    |
| `slow-operation-delay`     | `int`    | Simulated latency in ms (0/200/1000/3000) | `0`           |

### Chatbot Prompt Styles

The chatbot supports multiple prompt styles via GitHub Repository Prompts (`.prompt.yml` files):

- **expert**: Detailed Le Mans racing historian with comprehensive knowledge
- **casual**: Friendly enthusiast for casual conversation
- **brief**: Quick facts with concise responses
- **unreliable**: Confidently incorrect information (for A/B testing demos)

## Requirements

### Prerequisites

- .NET 10.0 SDK or later
- Python 3.14 or later
- Go 1.25 or later (for Feature Flags API)
- Node.js 22 or later (for React frontend)
- Visual Studio, Visual Studio Code with C# extension or JetBrains Rider
- Git for version control
- Docker Desktop (for containerized dependencies)
- Azure account (for Dev Tunnels authentication during development)
- [Foundry Local](https://learn.microsoft.com/azure/ai-foundry/foundry-local/get-started) (for chatbot functionality)

## Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/open-feature/openfeature-aspire-sample.git
cd openfeature-aspire-sample
```

### 2. Install Foundry Local (for Chatbot)

The chatbot runs the Phi-4-mini model on your machine through [Foundry Local](https://learn.microsoft.com/azure/ai-foundry/foundry-local/get-started). Aspire starts the service and downloads the model for you, but the CLI has to be installed first:

```bash
# macOS
brew tap microsoft/foundrylocal
brew trust microsoft/foundrylocal
brew install foundrylocal

# Windows
winget install Microsoft.FoundryLocal
```

> **Note:** The first run downloads the model weights, so it takes a few minutes. The dev container does not ship Foundry Local — run the app on the host if you need the chatbot. When the app is published, this resource becomes a provisioned Azure AI Foundry account instead, and the chat service authenticates with its managed identity.

### 3. Restore Dependencies

```bash
dotnet restore
```

### 4. Run with .NET Aspire

```bash
aspire run
```

> **Note**: The `aspire.config.json` in the repository root automatically points to the correct AppHost project, so you can run `aspire run` from the repository root.

### 5. Access the Application

- Web Frontend: [https://localhost:7070](https://localhost:7070)
- API Service: [https://localhost:7071](https://localhost:7071)
- Aspire Dashboard: [https://localhost:15888](https://localhost:15888)
- Grafana (LGTM): [http://localhost:3000](http://localhost:3000)

### Provisioned Grafana Dashboards

Grafana dashboard provisioning is configured in the AppHost and mounted into the LGTM container.

- Provider config: `src/Garage.AppHost/grafana/provisioning/dashboards/custom.yaml`
- Dashboard JSON folder: `src/Garage.AppHost/grafana/provisioning/dashboards/custom/`

To add an external dashboard:

1. Export or download the dashboard JSON.
2. Place it in `src/Garage.AppHost/grafana/provisioning/dashboards/custom/`.
3. Restart Aspire (`aspire run`) so LGTM reloads provisioned dashboards.
4. Open Grafana and navigate to the **OpenFeature** folder.

The starter dashboard includes datasource placeholder variables you can reuse in your panels:

- `$metrics_ds` (Prometheus)
- `$logs_ds` (Loki)
- `$traces_ds` (Tempo)

### 6. OpenAPI and Scalar Documentation (Development)

The API service exports an OpenAPI document in Development and serves a Scalar UI for interactive exploration.

- OpenAPI JSON: `https://localhost:7071/openapi/v1.json`
- Scalar UI: `https://localhost:7071/scalar/v1`

The exported OpenAPI includes:

- Endpoint summaries and descriptions
- Explicit success and problem response documentation
- Schema property descriptions for winner data

The application will start with flagd running as a container, providing OFREP endpoints for the React frontend, .NET API service, and Python chatbot to consume feature flags.

## Go Feature Flags API

The Go feature flags API (`Garage.FeatureFlags`) provides dynamic management of flag targeting rules:

- **Framework**: Standard library `net/http` with `otelhttp` instrumentation
- **Feature Flags**: OpenFeature Go SDK with OFREP provider
- **Storage**: Local filesystem or Azure Blob Storage (via gocloud.dev)
- **Telemetry**: Full OpenTelemetry integration (traces, metrics, logs)

### API Endpoints

```text
GET  /flags           # List all flag targeting configurations
PUT  /flags/{name}    # Update targeting rules for a flag
```

## Python Chat Service

The Python chat service (`Garage.ChatService`) provides an AI-powered chatbot for Le Mans racing questions:

- **Framework**: FastAPI with Uvicorn
- **AI Provider**: Microsoft Foundry (Phi-4-mini)
- **Feature Flags**: OpenFeature with OFREP provider
- **Telemetry**: Full OpenTelemetry integration (traces, metrics, logs)
- **Prompts**: GitHub Repository Prompts format (`.prompt.yml`)

### Chat API Endpoints

```text
POST /chat
Request: { "message": "Who won Le Mans in 2023?", "userId": "user-123" }
Response: { "response": "...", "prompt_style": "expert" }

GET /health
Response: { "status": "healthy" }
```

## Additional Resources

- [OpenFeature Documentation](https://docs.openfeature.dev/)
- [OFREP Specification](https://openfeature.dev/specification/ofrep)
- [flagd Documentation](https://flagd.dev/)
- [.NET Aspire Documentation](https://learn.microsoft.com/en-us/dotnet/aspire/)
- [Microsoft Foundry Documentation](https://learn.microsoft.com/azure/ai-foundry/)
- [Foundry Local Documentation](https://learn.microsoft.com/azure/ai-foundry/foundry-local/)
- [GitHub Repository Prompts](https://docs.github.com/en/github-models/use-github-models/storing-prompts-in-github-repositories)
- [Feature Flag Best Practices](https://martinfowler.com/articles/feature-toggles.html)

## License

This project is licensed under the [MIT License](LICENSE).
