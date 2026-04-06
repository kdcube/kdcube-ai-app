import os
import logging
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from kdcube_ai_app.apps.chat.external_log_collector.event_type import ExternalLogEvent
from kdcube_ai_app.apps.chat.external_log_collector.service import LogCollectorService
import kdcube_ai_app.apps.utils.logging_config as logging_config

_SERVICE_DIR = Path(__file__).resolve().parents[4]
os.environ.setdefault("LOG_DIR", str(_SERVICE_DIR))
os.environ.setdefault("LOG_FILE_PREFIX", "chat-frontend-logs")

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


if __name__ == "__main__":
    import uvicorn

    EVENTS_COLLECTOR_PORT = int(os.environ.get("EVENTS_COLLECTOR_PORT", 8080))

    logger.info(f"Starting External Log Collector on port {EVENTS_COLLECTOR_PORT}")

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=EVENTS_COLLECTOR_PORT,
        log_config=None,
    )