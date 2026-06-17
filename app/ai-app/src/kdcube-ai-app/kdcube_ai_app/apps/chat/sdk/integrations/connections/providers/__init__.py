"""Built-in ConnectionProvider declarations.

Importing this package registers all bundled providers via their
`@connection_provider(...)` decorators.
"""

from __future__ import annotations

from . import slack  # noqa: F401  (registers SlackConnection)
from . import gmail  # noqa: F401  (registers GmailConnection — Google OAuth)

__all__ = ["slack", "gmail"]
