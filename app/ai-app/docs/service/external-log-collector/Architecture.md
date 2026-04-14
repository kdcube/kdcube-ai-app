# External Log Collector — Architecture & Design

## Overview

**External Log Collector** — a system for intercepting, enriching, and persisting logs generated in the user's browser. The system automatically collects errors and warnings from `console.error`, `console.warn`, and unhandled exceptions, enriches them with contextual information (tenant, project, user, session, conversation), and sends them to the backend for centralized storage and analysis.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         React Frontend App                          │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │         Event Reporting Module (JavaScript)                  │  │
│  │                                                              │  │
│  │  ┌────────────────────────────────────────────────────────┐ │  │
│  │  │  1. Console Interceptor                                │ │  │
│  │  │     • Patches console.error                            │ │  │
│  │  │     • Patches console.warn                             │ │  │
│  │  │     • Listens to unhandledrejection events             │ │  │
│  │  │     • Preserves original behavior (transparent)        │ │  │
│  │  └────────────────────────────────────────────────────────┘ │  │
│  │                           ↓                                 │  │
│  │  ┌────────────────────────────────────────────────────────┐ │  │
│  │  │  2. Metadata Enricher                                  │ │  │
│  │  │     • Reads tenant & project from ChatSettings Redux   │ │  │
│  │  │     • Reads user_id & session_id from UserProfile      │ │  │
│  │  │     • Reads conversation_id from ChatState Redux       │ │  │
│  │  │     • Adds timestamp & timezone                        │ │  │
│  │  │     (Read from store at intercept time, not at init)   │ │  │
│  │  └────────────────────────────────────────────────────────┘ │  │
│  │                           ↓                                 │  │
│  │  ┌────────────────────────────────────────────────────────┐ │  │
│  │  │  3. Deduplication & Buffering                          │ │  │
│  │  │     • Dedup: same message within 5s sent once          │ │  │
│  │  │     • Buffer size: 50 events max                       │ │  │
│  │  │     • Errors: immediate flush (no wait)               │ │  │
│  │  │     • Warnings: batched flush every 5s                 │ │  │
│  │  │     • Fire-and-forget: if collector down → dropped     │ │  │
│  │  └────────────────────────────────────────────────────────┘ │  │
│  │                           ↓                                 │  │
│  │  ┌────────────────────────────────────────────────────────┐ │  │
│  │  │  4. Event Queue & Batch Sender                         │ │  │
│  │  │     • Collects multiple events                         │ │  │
│  │  │     • Sends as JSON batch via POST /events/client      │ │  │
│  │  │     • Automatic flush: every 5s or on error            │ │  │
│  │  └────────────────────────────────────────────────────────┘ │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                               ↓ HTTP POST
                      /events/client (JSON)
                               ↓
┌─────────────────────────────────────────────────────────────────────┐
│                External Log Collector Service                       │
│            (Standalone FastAPI/Flask microservice)                  │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  1. HTTP Endpoint Handler                                   │  │
│  │     • Route: POST /events/client                            │  │
│  │     • Accepts: batch of client events (JSON)                │  │
│  │     • Auth: validates tenant & user context                 │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                           ↓                                        │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  2. Event Validator                                         │  │
│  │     • Validates against Pydantic models                     │  │
│  │     • Enforces: ExternalLogEvent or ExternalMetricEvent    │  │
│  │     • Required fields: event_type, tenant, timestamp, etc.  │  │
│  │     • Type-safe: level, message, args for logs             │  │
│  │     • Type-safe: name, value, tags for metrics             │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                           ↓                                        │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  3. Python Logging Handler                                  │  │
│  │     • Creates structured JSON log entry                     │  │
│  │     • Log level: ERROR for client errors, INFO for metrics  │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                           ↓                                        │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  4. Log File Persistence                                    │  │
│  │     • Rotation: by size (10 MB or configurable)             │  │
│  │     • Retention: 5-10 recent files kept                     │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                           ↓                                        │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                               ↓
                    Disk Storage / External Systems
```

---

## Data Flow: Log Event Journey

### 1️⃣ **Capture** — In the Browser
```
User Action
     ↓
console.error("Failed to load") called
     ↓
Interceptor catches the call
     ↓
Enrich with: tenant, project, user_id, session_id, conversation_id, timestamp
     ↓
Check dedup: "error Failed to load" seen in last 5s? Skip if yes.
     ↓
Add to buffer
```

### 2️⃣ **Queue & Send** — Batching
```
Buffer has events (or 5 seconds elapsed, or error occurred)
     ↓
Flush: POST /events/client with batch of 1-50 events
     ↓
Server responds 200 OK
     ↓
Buffer cleared, ready for new events
```

### 3️⃣ **Receive & Validate** — Backend Service
```
POST /events/client received
     ↓
Validate each event against Pydantic model
     ↓
Reject invalid events (malformed, missing fields)
     ↓
Log valid events as JSON to file
     ↓
Return 200 OK (even if some events were invalid)
```

### 4️⃣ **Persist** — Storage
```
Event written to log file: logs/external_events.log
     ↓
File rotated when reaching size limit (10 MB)
     ↓
Old files kept: external_events.log.1, .log.2, etc.
     ↓
Ready for analysis, dashboards, alerting
```

---