# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

from __future__ import annotations


class ExternalEventLaneWakeIgnored(Exception):
    """Raised when a lane wake is valid but no processor turn should run."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = str(reason or "ignored")


class ExternalEventLaneTurnSuperseded(Exception):
    """Raised when a running turn lost ownership of its conversation event lane."""

    def __init__(
        self,
        *,
        turn_id: str,
        owner_turn_id: str = "",
        handler_status: str = "",
        conversation_id: str = "",
        phase: str = "",
    ) -> None:
        self.turn_id = str(turn_id or "")
        self.owner_turn_id = str(owner_turn_id or "")
        self.handler_status = str(handler_status or "")
        self.conversation_id = str(conversation_id or "")
        self.phase = str(phase or "")
        super().__init__(
            "external event lane turn superseded"
            f" turn_id={self.turn_id or '<empty>'}"
            f" owner_turn_id={self.owner_turn_id or '<empty>'}"
            f" handler_status={self.handler_status or '<empty>'}"
            f" phase={self.phase or '<empty>'}"
        )
