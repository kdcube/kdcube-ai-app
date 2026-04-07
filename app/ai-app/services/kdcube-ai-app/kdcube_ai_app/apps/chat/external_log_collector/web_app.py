import os
import logging
from pathlib import Path
from dotenv import load_dotenv, find_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from kdcube_ai_app.apps.chat.external_log_collector.event_type import ExternalLogEvent
from kdcube_ai_app.apps.chat.external_log_collector.service import LogCollectorService
import kdcube_ai_app.apps.utils.logging_config as logging_config

# Default component identity for shared .env usage
os.environ.setdefault("GATEWAY_COMPONENT", "collector")

_ENV_DIR = Path(__file__).resolve().parent
_CONFIG_DIR = os.environ.get("KDCUBE_CONFIG_DIR")
_IN_CONTAINER = Path("/.dockerenv").exists()

if _CONFIG_DIR:
    _CONFIG_ENV = Path(_CONFIG_DIR) / ".env.collector"
    if _CONFIG_ENV.exists():
        load_dotenv(_CONFIG_ENV, override=True)
elif not _IN_CONTAINER:
    # Local dev only (avoid overriding compose envs in containers).
    load_dotenv(_ENV_DIR / ".env.collector", override=True)

if not _IN_CONTAINER:
    load_dotenv(find_dotenv(usecwd=False))

logging_config.configure_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title="External Log Collector")

# Enable CORS for all origins (local dev)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize service
log_collector_service = LogCollectorService()


@app.post("/api/events/client")
async def receive_client_event(event: ExternalLogEvent):
    """Receive and process client-side log event"""
    try:
        log_collector_service.process(event)
        return {
            "status": "received",
            "event_type": event.event_type,
            "level": event.level,
        }
    except Exception as e:
        logger.error(f"Error processing client event: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to process event")


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "ok",
        "service": "external-log-collector",
        "port": EVENTS_COLLECTOR_PORT,
    }


# Get port from env (set by .env.collector or KDCUBE_CONFIG_DIR)
EVENTS_COLLECTOR_PORT = int(os.environ.get("EVENTS_COLLECTOR_PORT", 8080))


if __name__ == "__main__":
    import uvicorn

    logger.info(f"Starting External Log Collector on port {EVENTS_COLLECTOR_PORT}")

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=EVENTS_COLLECTOR_PORT,
        log_config=None,
    )