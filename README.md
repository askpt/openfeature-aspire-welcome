# OpenFeature Aspire Welcome

A sample application demonstrating the integration of [OpenFeature](https://openfeature.dev/) with [.NET Aspire](https://learn.microsoft.com/en-us/dotnet/aspire/get-started/aspire-overview) for feature flag management. This application uses the [flagd](https://flagd.dev/) provider to deliver feature flags to the applications in the solution.

## Overview

This project is a demonstration of how to integrate OpenFeature with .NET Aspire to create a powerful, cloud-native application with feature flag capabilities. The solution consists of:

- **Todo.Web**: A Blazor web application that consumes feature flags
- **Todo.ApiService**: An API service that also uses feature flags
- **Todo.AppHost**: The Aspire host that coordinates the application components
- **Todo.ServiceDefaults**: Common services and configurations used across the application
- **flagd**: A feature flag provider that serves feature flags to the application

## Features

- Integration of OpenFeature with .NET Aspire
- Feature flag management using flagd
- Sample feature flags demonstrating different use cases:
  - `use-new-counter-version`: Controls the counter increment behaviour in the web application
  - `return-weather-forecast`: Controls the number of weather forecasts returned by the API

## Prerequisites

- [.NET 9 SDK](https://dotnet.microsoft.com/download/dotnet/9.0) or later
- [Docker](https://www.docker.com/products/docker-desktop/) for running the services

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/askpt/openfeature-aspire-welcome.git
cd openfeature-aspire-welcome
```

### 2. Configure flagd source location

The application needs to know where the flagd configuration file is located. You need to set this using .NET user secrets:

```bash
cd Todo.AppHost
dotnet user-secrets init
dotnet user-secrets set "flagd:Source" "$(pwd)/../flagd"
```

> **Note for Unix-like systems**: This sets the absolute path to your flagd folder in the user secrets. The AppHost will use this path to mount the flagd configuration file to the container.
>
> **Note for Windows users**: If you are using PowerShell, replace `$(pwd)` with `$(Get-Location)` in the command above. For example:
>
> ```powershell
> dotnet user-secrets set "flagd:Source" "$(Get-Location)/../flagd"
> ```

### 3. Build and run the application

```bash
dotnet build
cd Todo.AppHost
dotnet run
```

The Aspire dashboard will open automatically, showing the status of all services. From there, you can navigate to the web application.

## Project Structure

- **Todo.Web**: Contains the frontend Blazor application
  - Uses the counter feature flag to demonstrate different behaviours
- **Todo.ApiService**: Contains the backend API service
  - Uses a feature flag to control the number of weather forecasts returned
- **Todo.AppHost**: The Aspire host application
  - Configures and orchestrates all services
  - Sets up the flagd container
- **Todo.ServiceDefaults**: Common configuration for all services
  - Configures OpenFeature, OpenTelemetry, and other cross-cutting concerns
- **flagd**: Contains the feature flag configuration

## Feature Flags

The application uses two feature flags:

1. **use-new-counter-version**:

   - When enabled, the counter will increase by a random value
   - When disabled, the counter will increase by 1

2. **return-weather-forecast**:
   - Controls how many weather forecasts the API returns (3 or 5)

## Modifying Feature Flags

You can modify the feature flags by editing the `flagd/flagd.json` file. After making changes, restart the application to see the effects.

## Additional Resources

- [OpenFeature Documentation](https://openfeature.dev/)
- [flagd Documentation](https://flagd.dev/)
- [.NET Aspire Documentation](https://learn.microsoft.com/en-us/dotnet/aspire/)
