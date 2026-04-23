---
id: ks:docs/service/external-log-collector/frontend-events-design.md
title: "Frontend Log Events Design"
summary: "Event schema and payload design for frontend log and metric events emitted by the browser and accepted by the backend collector."
tags: ["service", "frontend", "logging", "events", "observability", "design"]
keywords: ["frontend log event schema", "browser metric payloads", "client telemetry models", "log collector event contract", "frontend observability payload design"]
see_also:
  - ks:docs/service/external-log-collector/Architecture.md
  - ks:docs/service/README-monitoring-observability.md
---
# Frontend Log Events — Design

## Python models (backend)

```python
from __future__ import annotations
from datetime import datetime
from typing import Literal, Any
from pydantic import BaseModel


class EventBase(BaseModel):
    event_type: Literal["log", "metric"]

    tenant:          str
    project:         str
    user_id:         str | None
    session_id:      str | None
    conversation_id: str | None
    timestamp:       datetime        # ISO 8601 UTC
    timezone:        str


class ExternalLogEvent(EventBase):
    level:   Literal["error", "warn", "info"]
    message: str
    args:    list[Any]


class ExternalMetricEvent(EventBase):
    name:  str             # e.g. "chat.message.sent", "file.upload.size"
    value: float
    tags:  dict[str, str]  # arbitrary key-value labels


ExternalEvent = ExternalLogEvent | ExternalMetricEvent
```

## Log file examples

**log:**
```
2026-03-31 10:42:17,331 - kdcube.events - ERROR - {"event_type": "log", "tenant": "acme", "project": "sales-bot", "user_id": "u_8f3a1c", "session_id": "sess_4d9b22", "conversation_id": "conv_77e1a0", "timestamp": "2026-03-31T10:42:17.331000Z", "timezone": "UTC", "level": "error", "message": "Failed to load conversation history", "args": [{"status": 503, "url": "/api/conversations"}]}
```

**metric:**
```
2026-03-31 10:42:18,004 - kdcube.events - INFO - {"event_type": "metric", "tenant": "acme", "project": "sales-bot", "user_id": "u_8f3a1c", "session_id": "sess_4d9b22", "conversation_id": "conv_77e1a0", "timestamp": "2026-03-31T10:42:18.004000Z", "timezone": "UTC", "name": "chat.message.sent", "value": 1.0, "tags": {"bundle": "react-v2", "model": "claude-sonnet"}}
```

---
