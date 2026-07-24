# SPDX-License-Identifier: MIT

"""The legacy import path keeps working after the move to agentic_config."""


def test_legacy_import_path_serves_the_same_composer():
    from kdcube_ai_app.apps.chat.sdk.solutions.agentic_instructions import (
        compose_instruction_body as legacy,
    )
    from kdcube_ai_app.apps.chat.sdk.solutions.agentic_config.instructions import (
        compose_instruction_body as canonical,
    )

    assert legacy is canonical
