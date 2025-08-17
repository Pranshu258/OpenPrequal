import logging

from config.logging_config import setup_logging

# Set up logging at the start of the module
setup_logging()
logger = logging.getLogger(__name__)
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from config.config import Config
from contracts.backend import Backend
from contracts.probe_response import ProbeResponse
from core.heartbeat_client import HeartbeatClient
from core.load_sim_middleware import LoadSimMiddleware
from core.metrics_manager import MetricsManager

# Instantiate metrics manager
metrics_manager = MetricsManager()

backend = Backend(
    url=Config.BACKEND_URL,
    port=int(Config.BACKEND_PORT),
    health=True,
)

heartbeat_client = HeartbeatClient(
    backend=backend,
    proxy_url=Config.PROXY_URL,
    heartbeat_interval=Config.HEARTBEAT_SECONDS,
    metrics_manager=metrics_manager,
)


@asynccontextmanager
async def lifespan(app):
    await heartbeat_client.start()
    yield
    await heartbeat_client.stop()


app = FastAPI(lifespan=lifespan)

# Add RIF load simulation middleware before metrics middleware
app.add_middleware(LoadSimMiddleware, metrics_manager=metrics_manager)
app.middleware("http")(metrics_manager.prometheus_middleware)


@app.get("/")
async def read_root():
    return Response(
        content=f'{{"message": "Hello from backend at {Config.BACKEND_URL}!"}}',
        media_type="application/json",
        headers={"X-Backend-Id": Config.BACKEND_URL},
    )


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/probe", response_model=ProbeResponse)
def health_probe():
    logger.info(f"probe requested from {Config.BACKEND_URL}")
    probe_response = ProbeResponse(
        status="ok",
        in_flight_requests=int(metrics_manager.get_in_flight()),
        avg_latency=metrics_manager.get_avg_latency(),
    )
    return Response(
        content=probe_response.model_dump_json(),
        media_type="application/json",
        headers={"X-Backend-Id": Config.BACKEND_URL},
    )


# Example: log server startup
logger.info("Backend server module loaded and logging is configured.")
