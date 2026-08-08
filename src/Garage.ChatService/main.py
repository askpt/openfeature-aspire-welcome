"""Le Mans Chatbot Service - FastAPI application using Microsoft Foundry and OpenFeature."""

import os
import time
import logging
import json
from typing import Any
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit

import grpc

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import OpenAI
from openfeature import api
from openfeature.contrib.provider.ofrep import OFREPProvider
from openfeature.evaluation_context import EvaluationContext
from opentelemetry import trace, metrics
from opentelemetry._logs import set_logger_provider
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.resources import Resource, SERVICE_NAME as RESOURCE_SERVICE_NAME
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.trace import SpanKind

# Import GenAI semantic conventions for trace attributes
# The semantic-conventions package provides standardized attribute names
try:
    # Try the newer module path first
    from opentelemetry.semconv.gen_ai import GenAiOperationNameValues, GenAiSystemValues
    GENAI_OPERATION_CHAT = GenAiOperationNameValues.CHAT.value
    GENAI_PROVIDER_OPENAI = GenAiSystemValues.OPENAI.value
except ImportError:
    # Fallback to string literals if the semconv module is not available
    # These match the OpenTelemetry semantic conventions for GenAI
    GENAI_OPERATION_CHAT = "chat"
    GENAI_PROVIDER_OPENAI = "openai"

from prompt_loader import load_prompt, render_messages, get_model_parameters

# Get configuration from environment
OFREP_ENDPOINT = os.environ.get("OFREP_ENDPOINT", "http://localhost:8016")
# Microsoft Foundry connection from Aspire (uses format: {RESOURCE}_{PROPERTY}).
# Foundry Local injects CHAT_MODEL_KEY; Azure AI Foundry does not and expects a
# Microsoft Entra ID token from the service's managed identity instead.
CHAT_MODEL_ENDPOINT = os.environ.get("CHAT_MODEL_URI", "http://localhost:5273/v1")
# Foundry Local already exposes a complete OpenAI base URL, while Azure AI Foundry only exposes the
# account root, so the AppHost supplies the extra "openai/v1" segment in publish mode.
CHAT_MODEL_API_PATH = os.environ.get("CHAT_MODEL_API_PATH", "")
CHAT_MODEL_KEY = os.environ.get("CHAT_MODEL_KEY", "")
CHAT_MODEL_NAME = os.environ.get("CHAT_MODEL_MODELNAME", "phi-4-mini")
CHAT_MODEL_SCOPE = os.environ.get("CHAT_MODEL_SCOPE", "https://cognitiveservices.azure.com/.default")
CHAT_MODEL_BASE_URL = "/".join(
    part for part in (CHAT_MODEL_ENDPOINT.rstrip("/"), CHAT_MODEL_API_PATH.strip("/")) if part
)
# OpenTelemetry configuration from Aspire
OTLP_ENDPOINT = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "")
SERVICE_NAME = os.environ.get("OTEL_SERVICE_NAME", "chatservice")
CAPTURE_MESSAGE_CONTENT = os.environ.get("OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT", "false").lower() in {"1", "true", "yes", "on"}
# CORS configuration - allow specific origins from environment, default to localhost dev servers
CORS_ORIGINS = os.environ.get("CORS_ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:5174").split(",")
PROMPTS_DIR = Path(__file__).parent / "prompts"

# Telemetry values derived from the resolved model endpoint.
_CHAT_MODEL_URL = urlsplit(CHAT_MODEL_ENDPOINT)
CHAT_MODEL_SERVER_ADDRESS = _CHAT_MODEL_URL.hostname or "localhost"
CHAT_MODEL_SERVER_PORT = _CHAT_MODEL_URL.port or (443 if _CHAT_MODEL_URL.scheme == "https" else 80)
# Foundry Local is a plain OpenAI-compatible server; Azure AI Foundry reports as azure.ai.openai.
GENAI_PROVIDER_NAME = GENAI_PROVIDER_OPENAI if CHAT_MODEL_KEY else "azure.ai.openai"

# Metrics - initialized after setup_telemetry
chat_request_counter = None
chat_request_duration = None

# Configure basic logging first (will be enhanced by OTLP later)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value)


def _build_semconv_payloads(messages: list[dict[str, Any]]) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    """Build GenAI semconv-compatible system instructions and input messages."""
    system_instructions: list[dict[str, str]] = []
    input_messages: list[dict[str, Any]] = []

    for message in messages:
        role = message.get("role", "user")
        content = _as_text(message.get("content"))

        if role == "system":
            if content:
                system_instructions.append({"type": "text", "content": content})
            continue

        parts: list[dict[str, Any]] = []
        if content:
            parts.append({"type": "text", "content": content})

        # Preserve tool call data if present in chat history.
        for tool_call in message.get("tool_calls", []) or []:
            parts.append(
                {
                    "type": "tool_call",
                    "id": _as_text(tool_call.get("id")),
                    "name": _as_text(tool_call.get("function", {}).get("name")),
                    "arguments": _as_text(tool_call.get("function", {}).get("arguments")),
                }
            )

        if parts:
            input_messages.append({"role": role, "parts": parts})

    return system_instructions, input_messages


def setup_telemetry():
    """Configure OpenTelemetry tracing, metrics, and logging using gRPC exporter."""
    global chat_request_counter, chat_request_duration

    # Create resource with service name
    resource = Resource.create({
        RESOURCE_SERVICE_NAME: SERVICE_NAME
    })

    if not OTLP_ENDPOINT:
        logger.warning("OTEL_EXPORTER_OTLP_ENDPOINT not set, using no-op telemetry")
        # Create metrics even without export endpoint for local tracking
        meter = metrics.get_meter(__name__)
        chat_request_counter = meter.create_counter(
            name="chat_requests_total",
            description="Total number of chat requests",
            unit="1"
        )
        chat_request_duration = meter.create_histogram(
            name="chat_request_duration_seconds",
            description="Duration of chat requests in seconds",
            unit="s"
        )
        return

    logger.info(f"Configuring OpenTelemetry with endpoint: {OTLP_ENDPOINT}")

    # Parse endpoint - Aspire provides HTTPS endpoint, we need to handle it
    endpoint = OTLP_ENDPOINT

    # For gRPC, we need just host:port without the scheme
    if endpoint.startswith("https://"):
        grpc_endpoint = endpoint.replace("https://", "")
        use_tls = True
    elif endpoint.startswith("http://"):
        grpc_endpoint = endpoint.replace("http://", "")
        use_tls = False
    else:
        grpc_endpoint = endpoint
        use_tls = False

    logger.info(f"OTLP gRPC endpoint: {grpc_endpoint}, TLS: {use_tls}")

    try:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
        from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter

        # Determine credentials for TLS
        credentials = None
        if use_tls:
            ca_cert_path = os.environ.get("SSL_CERT_FILE", "")
            if ca_cert_path and os.path.exists(ca_cert_path):
                logger.info(f"Using CA cert from SSL_CERT_FILE: {ca_cert_path}")
                with open(ca_cert_path, "rb") as f:
                    ca_cert = f.read()
                credentials = grpc.ssl_channel_credentials(root_certificates=ca_cert)

        # Setup tracing
        if use_tls and credentials:
            trace_exporter = OTLPSpanExporter(endpoint=grpc_endpoint, credentials=credentials)
        else:
            trace_exporter = OTLPSpanExporter(endpoint=grpc_endpoint, insecure=True)

        trace_provider = TracerProvider(resource=resource)
        trace_provider.add_span_processor(BatchSpanProcessor(trace_exporter))
        trace.set_tracer_provider(trace_provider)

        # Setup metrics
        if use_tls and credentials:
            metric_exporter = OTLPMetricExporter(endpoint=grpc_endpoint, credentials=credentials)
        else:
            metric_exporter = OTLPMetricExporter(endpoint=grpc_endpoint, insecure=True)

        metric_reader = PeriodicExportingMetricReader(metric_exporter, export_interval_millis=10000)
        meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
        metrics.set_meter_provider(meter_provider)

        # Setup logging export to OTLP
        if use_tls and credentials:
            log_exporter = OTLPLogExporter(endpoint=grpc_endpoint, credentials=credentials)
        else:
            log_exporter = OTLPLogExporter(endpoint=grpc_endpoint, insecure=True)

        logger_provider = LoggerProvider(resource=resource)
        logger_provider.add_log_record_processor(BatchLogRecordProcessor(log_exporter))
        set_logger_provider(logger_provider)

        # Add OTLP handler to root logger to export logs
        otlp_handler = LoggingHandler(level=logging.INFO, logger_provider=logger_provider)
        logging.getLogger().addHandler(otlp_handler)

        # Instrument logging to add trace context to logs
        LoggingInstrumentor().instrument(set_logging_format=True)

        # Create metrics
        meter = metrics.get_meter(__name__)
        chat_request_counter = meter.create_counter(
            name="chat_requests_total",
            description="Total number of chat requests",
            unit="1"
        )
        chat_request_duration = meter.create_histogram(
            name="chat_request_duration_seconds",
            description="Duration of chat requests in seconds",
            unit="s"
        )

        logger.info(f"OpenTelemetry configured successfully for service: {SERVICE_NAME}")

    except Exception as e:
        logger.error(f"Failed to configure OpenTelemetry: {e}")
        # Create fallback metrics
        meter = metrics.get_meter(__name__)
        chat_request_counter = meter.create_counter(
            name="chat_requests_total",
            description="Total number of chat requests",
            unit="1"
        )
        chat_request_duration = meter.create_histogram(
            name="chat_request_duration_seconds",
            description="Duration of chat requests in seconds",
            unit="s"
        )


def setup_openfeature():
    """Configure OpenFeature with OFREP provider."""
    provider = OFREPProvider(base_url=OFREP_ENDPOINT)
    api.set_provider(provider)
    logger.info(f"OpenFeature configured with OFREP endpoint: {OFREP_ENDPOINT}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    setup_telemetry()
    setup_openfeature()
    logger.info("Chat service started")
    yield
    logger.info("Chat service shutting down")


# Create FastAPI app
app = FastAPI(
    title="Le Mans Chatbot",
    description="A chatbot that answers questions about Le Mans 24 Hours racing",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware - use configurable origins for security
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Instrument FastAPI with OpenTelemetry
FastAPIInstrumentor.instrument_app(app)

# Create the OpenAI-compatible client for the configured Microsoft Foundry endpoint.
# Foundry Local injects a static API key; Azure AI Foundry authenticates with Microsoft Entra ID,
# and the OpenAI SDK refreshes the bearer token on every request through the provider callable.
openai_client = OpenAI(
    base_url=CHAT_MODEL_BASE_URL,
    api_key=CHAT_MODEL_KEY or get_bearer_token_provider(DefaultAzureCredential(), CHAT_MODEL_SCOPE)
)


class ChatRequest(BaseModel):
    """Request model for chat endpoint."""
    message: str
    userId: str = "anonymous"


class ChatResponse(BaseModel):
    """Response model for chat endpoint."""
    response: str
    prompt_style: str


class HealthResponse(BaseModel):
    """Response model for health endpoint."""
    status: str


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(status="healthy")


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Chat endpoint that uses Microsoft Foundry with dynamic prompt selection."""
    start_time = time.time()

    tracer = trace.get_tracer(__name__)

    with tracer.start_as_current_span("chat_request") as span:
        client = api.get_client()

        # Create evaluation context with user ID
        eval_context = EvaluationContext(
            targeting_key=request.userId,
            attributes={"userId": request.userId}
        )
        span.set_attribute("user.id", request.userId)

        # Check if chatbot is enabled
        chatbot_enabled = client.get_boolean_value("enable-chatbot", True, eval_context)
        span.set_attribute("feature.enable_chatbot", chatbot_enabled)

        if not chatbot_enabled:
            # Record metric for disabled requests
            if chat_request_counter:
                chat_request_counter.add(1, {"status": "disabled", "prompt_style": "none"})
            raise HTTPException(
                status_code=503,
                detail="Chatbot is currently disabled"
            )

        # Get the prompt file to use
        prompt_file = client.get_string_value("prompt-file", "expert", eval_context)
        span.set_attribute("feature.prompt_file", prompt_file)
        logger.info(f"Using prompt file: {prompt_file} for user: {request.userId}")

        DEFAULT_PROMPT = "expert"

        try:
            # Load and render the prompt
            with tracer.start_as_current_span("load_prompt"):
                try:
                    prompt = load_prompt(prompt_file, str(PROMPTS_DIR))
                    effective_prompt_style = prompt_file
                except FileNotFoundError:
                    if prompt_file == DEFAULT_PROMPT:
                        raise
                    logger.warning(
                        f"Prompt file '{prompt_file}' not found; falling back to '{DEFAULT_PROMPT}'"
                    )
                    span.set_attribute("feature.prompt_file_fallback", DEFAULT_PROMPT)
                    prompt = load_prompt(DEFAULT_PROMPT, str(PROMPTS_DIR))
                    effective_prompt_style = DEFAULT_PROMPT
                messages = render_messages(prompt, {"message": request.message})
                model_params = get_model_parameters(prompt)

            # Call the Microsoft Foundry chat model
            with tracer.start_as_current_span("chat_model_call", kind=SpanKind.CLIENT) as model_span:
                # Legacy attributes for backward compatibility
                model_span.set_attribute("model", CHAT_MODEL_NAME)
                model_span.set_attribute("temperature", model_params.get("temperature", 0.7))

                # GenAI semantic conventions for Aspire dashboard visualization
                model_span.set_attribute("gen_ai.operation.name", GENAI_OPERATION_CHAT)
                model_span.set_attribute("gen_ai.provider.name", GENAI_PROVIDER_NAME)
                model_span.set_attribute("gen_ai.request.model", CHAT_MODEL_NAME)
                model_span.set_attribute("gen_ai.request.temperature", model_params.get("temperature", 0.7))
                model_span.set_attribute("server.address", CHAT_MODEL_SERVER_ADDRESS)
                model_span.set_attribute("server.port", CHAT_MODEL_SERVER_PORT)

                # Optional sensitive-content capture for GenAI visualizer.
                if CAPTURE_MESSAGE_CONTENT:
                    system_instructions, input_messages = _build_semconv_payloads(messages)
                    if system_instructions:
                        model_span.set_attribute("gen_ai.system_instructions", json.dumps(system_instructions))
                    if input_messages:
                        model_span.set_attribute("gen_ai.input.messages", json.dumps(input_messages))

                response = openai_client.chat.completions.create(
                    model=CHAT_MODEL_NAME,
                    messages=messages,
                    temperature=model_params.get("temperature", 0.7)
                )

                if not response.choices:
                    raise ValueError("No choices returned from AI model")
                answer = response.choices[0].message.content or ""
                model_span.set_attribute("response_length", len(answer))

                # Add GenAI response attributes
                if response.choices[0].finish_reason:
                    model_span.set_attribute("gen_ai.response.finish_reasons", [response.choices[0].finish_reason])
                if hasattr(response, 'model') and response.model:
                    model_span.set_attribute("gen_ai.response.model", response.model)

                if CAPTURE_MESSAGE_CONTENT:
                    output_parts = [{"type": "text", "content": answer}] if answer else []

                    for tool_call in getattr(response.choices[0].message, "tool_calls", []) or []:
                        output_parts.append(
                            {
                                "type": "tool_call",
                                "id": _as_text(getattr(tool_call, "id", "")),
                                "name": _as_text(getattr(getattr(tool_call, "function", None), "name", "")),
                                "arguments": _as_text(getattr(getattr(tool_call, "function", None), "arguments", "")),
                            }
                        )

                    output_messages = [
                        {
                            "role": "assistant",
                            "parts": output_parts,
                            "finish_reason": response.choices[0].finish_reason,
                        }
                    ]
                    model_span.set_attribute("gen_ai.output.messages", json.dumps(output_messages))

                # Add token usage metrics if available
                if hasattr(response, 'usage') and response.usage:
                    if hasattr(response.usage, 'prompt_tokens') and response.usage.prompt_tokens is not None:
                        model_span.set_attribute("gen_ai.usage.input_tokens", response.usage.prompt_tokens)
                    if hasattr(response.usage, 'completion_tokens') and response.usage.completion_tokens is not None:
                        model_span.set_attribute("gen_ai.usage.output_tokens", response.usage.completion_tokens)

            # Record successful request metrics
            duration = time.time() - start_time
            if chat_request_counter:
                chat_request_counter.add(1, {"status": "success", "prompt_style": effective_prompt_style})
            if chat_request_duration:
                chat_request_duration.record(duration, {"prompt_style": effective_prompt_style})

            return ChatResponse(response=answer, prompt_style=effective_prompt_style)

        except FileNotFoundError:
            logger.error(f"Prompt file not found: {prompt_file} (and fallback '{DEFAULT_PROMPT}' also missing)")
            if chat_request_counter:
                chat_request_counter.add(1, {"status": "error", "prompt_style": prompt_file})
            raise HTTPException(
                status_code=503,
                detail="Chat service is temporarily unavailable: prompt configuration is missing"
            )
        except Exception as e:
            logger.error(f"Error calling the chat model: {e}")
            if chat_request_counter:
                chat_request_counter.add(1, {"status": "error", "prompt_style": prompt_file})
            raise HTTPException(
                status_code=500,
                detail="Error processing chat request"
            )


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
