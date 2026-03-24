# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Elena Viter
#
# Event filter for the OpenRouter data-processing bundle.
# Controls which SSE events are forwarded to the client.

from typing import Optional, Dict, Any
from kdcube_ai_app.apps.chat.sdk.comm.event_filter import IEventFilter, EventFilterInput


class BundleEventFilter(IEventFilter):
    """Simple pass-through filter — forward all events to the client."""

    def allow_event(
        self,
        *,
        user_type: str,
        user_id: str,
        event: EventFilterInput,
        data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        return True