# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Elena Viter

# kdcube_ai_app/apps/chat/sdk/runtime/solution/react/agents/ver2/decision.py

import logging
from typing import Any, Dict, List, Optional, Literal
from pydantic import BaseModel, Field
from kdcube_ai_app.infra.service_hub.inventory import (
    ModelServiceBase,
    create_cached_system_message,
    create_cached_human_message,
)
from kdcube_ai_app.infra.service_hub.errors import ServiceException, ServiceError, ServiceKind
from kdcube_ai_app.apps.chat.sdk.streaming.versatile_streamer import (
    ChannelSpec,
    stream_with_channels,
)
from kdcube_ai_app.apps.chat.sdk.solutions.react.decision_prompt import (
    compose_decision_system_text,
    head_tail_preview,
)

_LOG = logging.getLogger("agent.react.v2.decision")

class ToolCallDecisionV2(BaseModel):
    tool_id: str = Field(..., description="Qualified tool ID")
    params: Dict[str, Any] = Field(default_factory=dict)


class ReactDecisionOutV2(BaseModel):
    action: Literal["call_tool", "complete", "exit"]

    notes: str = ""

    # One action object, one tool call:
    # One ReactDecisionOutV2 object supports exactly one tool call object.
    # Multi-action output, when supported by the runtime, is represented by
    # multiple ReactDecisionOutV2 channel instances, not by arrays in this field.
    tool_call: Optional[ToolCallDecisionV2] = None

    final_answer: Optional[str] = None
    suggested_followups: Optional[List[str]] = None

def build_decision_system_text(
    *,
    adapters: List[Dict[str, Any]],
    infra_adapters: Optional[List[Dict[str, Any]]] = None,
    workspace_implementation: str = "custom",
    additional_instructions: Optional[str] = None,
    instruction_body: Optional[str] = None,
    instruction_blocks: Optional[List[str]] = None,
    include_tool_catalog: bool = True,
    include_skill_gallery: bool = True,
    skill_consumer: str = "solver.react.v2.decision.v2.strong",
) -> str:
    json_hint = (
        "{\n"
        "  \"action\": \"call_tool | complete | exit\",\n"
        "  \"notes\": \"Short user-visible progress note for tool rounds; empty for complete/exit\",\n"
        "  \"tool_call\": {\n"
        "    \"tool_id\": \"web_tools.web_search\",\n"
        "    \"params\": {<tool params according to tool documentation. to bind artifact content, set the param value to 'ref:<artifact_path_or_visible_file_path>'>},\n"
        "  },\n"
        "  \"final_answer\": \"(required for complete/exit)\",\n"
        "  \"suggested_followups\": [\"optional suggested follow-ups\"]\n"
        "}\n"
        "\n"
        "Each JSON object may contain at most ONE tool_call object.\n"
        "Do NOT emit a sequence/array/list of tool calls inside one ReactDecisionOutV2 object.\n"
        "If the runtime allows multiple actions in one round, emit each action in its own separate <channel:ReactDecisionOutV2> instance.\n"
    )

    # protocol = (
    #     "CRITICAL: you are the agent which must for in custom protocol which you must obey. This is not similar to tool calling protocol. You MUST NOT include multiple actions at a time in your response. This is a gross mistake.\n"
    #     "CRITICAL: you have 4 channel types. Three are required every round; summary is allowed ONLY on complete/exit final-answer rounds.\n"
    #     "Output protocol (strict): you must produce content which represents one round and consists of these required channels. Do not include summary unless action is complete or exit:\n"
    #     "<channel:thinking> ... </channel:thinking>\n"
    #     "<channel:ReactDecisionOutV2> ... </channel:ReactDecisionOutV2>\n"
    #     "<channel:code> code generated </channel:code>\n\n"
    #     "In a single round, exactly one occurrence of <channel:thinking>, <channel:ReactDecisionOutV2>, and <channel:code> can be included in your response.\n"
    #     "The optional <channel:summary> may appear exactly once, and only when the ReactDecisionOutV2 action is complete or exit.\n"
    #     "In <channel:thinking>, write a brief user-facing status in markdown\n"
    #     "The thinking <channel:thinking> channel is shown to the user.\n"
    #     "Keep it very short (1–2 sentences, no lists).\n\n"
    #     "<channel:ReactDecisionOutV2> is the action channel. One <channel:ReactDecisionOutV2> ... </channel:ReactDecisionOutV2> channel instance means exactly one action.\n"
    #     # "For now we support only one action per round, so the whole response must contain exactly one action total.\n"
    #     "Inside that single <channel:ReactDecisionOutV2> channel instance, output exactly one ```json fenced block with a ReactDecisionOutV2 object matching the shape hint below (no extra text):\n"
    #     "```json\n"
    #     f"{json_hint}\n"
    #     "```\n\n"
    #     "CRITICAL: The runtime which read your response will attempt to convert it to one round, so to one sequence of <channel:thinking>, <channel:ReactDecisionOutV2>, <channel:code>, and final-only optional <channel:summary>.\n"
    #     # "So a round is exactly one <channel:thinking> block + one <channel:ReactDecisionOutV2> block + one <channel:code> block.\n"
    #     # "After you generate these 3 channels, STOP. If you tempt to plan the multiple steps than simply use the plan tool for that. But never generate multiple rounds of thinking/ReactDecisionOutV2 - the runtime which will read your response will reject it fully if it contain more than 1 triplet of channels.\n"
    #     "DO NOT DO THIS: Your typical error is that you make sequence of channel groups <channel:thinking></channel:thinking><channel:ReactDecisionOutV2></channel:ReactDecisionOutV2><channel:code></channel:code> and then again <channel:thinking></channel:thinking><channel:ReactDecisionOutV2></channel:ReactDecisionOutV2><channel:code></channel:code> in the same response.\n"
    #     "DO NOT DO THIS: Your second typical error is that you include multiple JSON objects or fenced JSON blocks inside the single <channel:ReactDecisionOutV2> instance, like <channel:ReactDecisionOutV2>```json...```\n```json...```</channel:ReactDecisionOutV2>. This does not work in single-action mode. Emit exactly one tool call now and continue in a later round if more tools are needed.\n"
    #     # "Do not start a second thinking/ReactDecisionOutV2/code sequence in the same response, even as a correction or next step. Your runtime will reject the entire output as a protocol violation if in your response will be more that 1 instance of each channel.\n"
    #     # "Your typical error is that you make sequence of triplets <channel:thinking></channel:thinking><channel:ReactDecisionOutV2></channel:ReactDecisionOutV2><channel:code></channel:code> and then again <channel:thinking></channel:thinking><channel:ReactDecisionOutV2></channel:ReactDecisionOutV2><channel:code></channel:code> in the same response.\n"
    #     # "This is WRONG! You must produce only one triplet of channels per response."
    #     "If you need plan, plan with the plan tool or include it in notes but you are disallowed to call more than one tool. Generating the second instance of any channel in the same response means you do not understand the contract and violate it.\n\n"
    #     "Minimal valid shape:\n"
    #     "<channel:thinking>...short status...</channel:thinking>\n"
    #     "<channel:ReactDecisionOutV2>```json { ...one ReactDecisionOutV2 object... } ```</channel:ReactDecisionOutV2>\n"
    #     "<channel:code></channel:code>\n\n"
    #     "Final answer shape only when action is complete or exit:\n"
    #     "<channel:thinking>...short final status...</channel:thinking>\n"
    #     "<channel:ReactDecisionOutV2>```json { ...one complete/exit ReactDecisionOutV2 object... } ```</channel:ReactDecisionOutV2>\n"
    #     "<channel:code></channel:code>\n"
    #     "<channel:summary>Goal: ...\nOutcome: ...\nKey facts: ...\nRefs: ...</channel:summary>\n\n"
    #     "In <channel:code>, output ONLY the raw Python code snippet (no fencing, no any auxiliary text).\n"
    #     "Use <channel:code> only when the single action is exec_tools.execute_code_python; otherwise emit an empty <channel:code></channel:code> block.\n"
    #     "CRITICAL: Exec tool DOES NOT HAVE code parameter! Putting code in the tool call params is WRONG. Code goes only in <channel:code>!\n"
    #     "For call_tool actions, omit <channel:summary> entirely. For complete/exit actions, include exactly one <channel:summary> with a compact durable working summary using this shape: Goal, Outcome, Key facts, Refs. Refs should be logical paths for the user prompt, decisive tool calls/results, produced artifacts, and the assistant completion when known. This summary is for future cold-start continuity, not for the user-facing final_answer.\n"
    #     "CRITICAL: if you want to cite the channel name, i.e. if you by some reason decide to write the token which is verbatim a name one of the channels in your contract, for example, <channel:thinking>, while simply cite it as a name, not intending to open or close this channel, you MUST write it in backticks like this: `channel:CHANNEL_ID`; to avoid confusion with the actual channel opening/closing token.\n"
    # )
    protocol = (
        "CRITICAL: you are the agent which must form output in custom protocol which you must obey. This is not similar to tool calling protocol.\n"
        "CRITICAL: the first literal channel in your response must be <channel:thinking>. Never emit legacy <thinking>...</thinking> tags.\n"
        "CRITICAL: you have 4 channel types. Three are required every round; summary is allowed ONLY on complete/exit final-answer rounds.\n"
        "Output protocol (strict): you must produce content which represents one round and consists of these required channel types. Do not include summary unless action is complete or exit:\n"
        "<channel:thinking> ... </channel:thinking>\n"
        "<channel:ReactDecisionOutV2> ... </channel:ReactDecisionOutV2>\n"
        "<channel:code> code generated </channel:code>\n\n"
        "In a single round, include exactly one <channel:thinking>, one or more <channel:ReactDecisionOutV2> channel instances, and <channel:code> only when an exec action needs Python.\n"
        "The optional <channel:summary> may appear exactly once, and only when the response contains a single complete/exit action and no tool-call actions.\n"
        "In <channel:thinking>, write a brief user-facing status in markdown.\n"
        "The thinking <channel:thinking> channel is shown to the user.\n"
        "Keep it very short (1–2 sentences, no lists).\n\n"
        "<channel:ReactDecisionOutV2> is the action channel. One <channel:ReactDecisionOutV2> ... </channel:ReactDecisionOutV2> channel instance means exactly one action.\n"
        "If you need multiple actions in one round, repeat <channel:ReactDecisionOutV2>; if one action is exec_tools.execute_code_python, put its <channel:code> immediately after that exec decision. Do NOT generate a second <channel:thinking> in the same response.\n"
        "Inside each <channel:ReactDecisionOutV2> channel instance, output exactly one ```json fenced block with one ReactDecisionOutV2 object matching the shape hint below (no extra text):\n"
        "```json\n"
        f"{json_hint}\n"
        "```\n\n"
        "If you need multiple actions in one round, use this shape:\n"
        "<channel:thinking>...short status for the whole round...</channel:thinking>\n"
        "<channel:ReactDecisionOutV2>```json {{ ...first ReactDecisionOutV2 object... }} ```</channel:ReactDecisionOutV2>\n"
        "<channel:ReactDecisionOutV2>```json {{ ...exec_tools.execute_code_python action with params.contract... }} ```</channel:ReactDecisionOutV2>\n"
        "<channel:code>raw Python for the immediately preceding exec action</channel:code>\n"
        "<channel:ReactDecisionOutV2>```json {{ ...another independent non-exec action... }} ```</channel:ReactDecisionOutV2>\n\n"
        "Never put > 1 actions into one ReactDecisionOutV2 channel instance.\n"
        "Never put > 1 JSON objects, > 1 fenced JSON blocks, or prose after the JSON inside one <channel:ReactDecisionOutV2> instance.\n"
        "DO NOT DO THIS: Your second typical error is that you include a sequence of tool calls inside a single <channel:ReactDecisionOutV2> instance, like <channel:ReactDecisionOutV2>```json...```\n```json...```</channel:ReactDecisionOutV2>. This does not work. For each tool call, emit a separate <channel:ReactDecisionOutV2>...</channel:ReactDecisionOutV2> instance.\n"
        "If you emit multiple tool-call actions, each action must be in its own separate <channel:ReactDecisionOutV2>...</channel:ReactDecisionOutV2> instance.\n"
        "Use multi-action only when every action can be planned fully from the context already visible before the round starts.\n"
        "The runtime executes the actions sequentially and you do NOT review intermediate results in the middle, so action B must not depend on action A's result.\n"
        "Dependency/review barrier: if a later action would use anything produced or retrieved by an earlier action (artifact, source row, path, id, URL, code, data, or state), stop after the producing/retrieving action. In a later round, review the visible result and acknowledge both its existence and suitability before passing it to any downstream tool.\n"
        "Example: generate/write a document source first; after the write result is visible in the next round, review it, then render it. Do not generate and render that new source in the same response.\n"
        "Keep same-round tool-call sequences short. Use more than two tool-call actions only for a specific reason and only when every action is independent; long chains increase partial-failure risk and can damage downstream generation.\n"
        "Visibility rule: if generated content is meant for the user to see, download, approve, or use as a renderer source, make it external: react.write channel=canvas or exec visibility=external. Use channel=internal only for private scratch that will not be presented or rendered for the user.\n"
        "Default write rule: reports, briefs, HTML, Markdown, slide source, DOCX/PDF/PPTX source, and anything under outputs/ that may become a deliverable must be written with react.write channel=canvas. Do not write these as channel=internal.\n"
        "Renderer source rule: rendering_tools.write_* produces user-visible artifacts, so content='ref:...' must point to an external artifact that has passed the dependency/review barrier. Do not use channel=internal refs as PDF/PPTX/DOCX/PNG sources. For source documents that will be rendered for the user, write them first with react.write channel=canvas, or produce them from exec with visibility=external; then review before rendering. Use the input type documented by the target rendering tool.\n"
        "Exec binding: an exec_tools.execute_code_python decision must be followed immediately by <channel:code> containing its raw Python. That code binds only to the immediately preceding exec decision; if another decision appears before code, the exec action is incomplete and will not run.\n"
        "Exec in multi-action: you may include exactly one exec_tools.execute_code_python action together with other actions only when that exec decision has params.contract and is immediately followed by complete Python in <channel:code>. Otherwise exec must be the only action in the round.\n"
        "Do NOT mix complete/exit with tool calls in the same multi-action response.\n"
        "For complete/exit JSON, set notes=\"\" and tool_call=null. Put the user response only in final_answer; the only extra final-only channel is summary.\n"
        "Final answer shape only when action is complete or exit:\n"
        "<channel:thinking>...short final status...</channel:thinking>\n"
        "<channel:ReactDecisionOutV2>```json {{ ...one complete/exit ReactDecisionOutV2 object... }} ```</channel:ReactDecisionOutV2>\n"
        "<channel:code></channel:code>\n"
        "<channel:summary>Goal: ...\nOutcome: ...\nKey facts: ...\nRefs: ...</channel:summary>\n\n"
        "In <channel:code>, output ONLY the raw Python code snippet (no fencing, no any auxiliary text).\n"
        "Use non-empty <channel:code> only immediately after an exec_tools.execute_code_python decision. If there is no exec action, omit <channel:code> or emit an empty <channel:code></channel:code> block.\n"
        "CRITICAL: Exec tool DOES NOT HAVE code parameter! Putting code in the tool call params is WRONG. Code goes only in <channel:code>!\n"
        "For call_tool-only rounds, omit <channel:summary> entirely. For complete/exit rounds, include exactly one <channel:summary> with a compact durable working summary using this shape: Goal, Outcome, Key facts, Refs. Scale the summary to the turn: for trivial exchanges (greeting, acknowledgment, tiny answer), make it super short, often one line or a few words per field; do not make it look like heavy reasoning happened. Refs should be logical paths for the user prompt, decisive tool calls/results, produced artifacts, and the assistant completion when known. This summary is for future cold-start continuity, not for the user-facing final_answer.\n"
        "CRITICAL: if you want to cite the channel name, i.e. if you by some reason decide to write the token which is verbatim a name one of the channels in your contract, for example, <channel:thinking>, while simply cite it as a name, not intending to open or close this channel, you MUST write it in backticks like this: `channel:CHANNEL_ID`; to avoid confusion with the actual channel opening/closing token.\n"
    )
    sys_msg = compose_decision_system_text(
        protocol=protocol,
        module_label="ReAct Decision Module v2",
        adapters=adapters or [],
        infra_adapters=infra_adapters or [],
        workspace_implementation=workspace_implementation,
        additional_instructions=additional_instructions,
        skill_consumer=skill_consumer,
        instruction_body=instruction_body,
        instruction_blocks=instruction_blocks,
        include_tool_catalog=include_tool_catalog,
        include_skill_gallery=include_skill_gallery,
    )
    extra_instructions = str(additional_instructions or "").strip()
    if extra_instructions:
        head, tail = head_tail_preview(extra_instructions)
        _LOG.info(
            "[react.v2.decision] agent admin customization applied len=%s head=%r tail=%r",
            len(extra_instructions),
            head,
            tail,
        )
    else:
        _LOG.info("[react.v2.decision] agent admin customization not provided")
    return sys_msg


async def react_decision_stream_v2(
    svc: ModelServiceBase,
    *,
    agent_name: str,
    adapters: List[Dict[str, Any]],
    infra_adapters: Optional[List[Dict[str, Any]]] = None,
    workspace_implementation: str = "custom",
    additional_instructions: Optional[str] = None,
    instruction_body: Optional[str] = None,
    instruction_blocks: Optional[List[str]] = None,
    include_tool_catalog: bool = True,
    include_skill_gallery: bool = True,
    on_progress_delta=None,
    on_raw_delta=None,
    subscribers: Optional[Dict[str, List[Any]]] = None,
    max_tokens: int = 6000,
    user_blocks: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    system_text = build_decision_system_text(
        adapters=adapters,
        infra_adapters=infra_adapters,
        workspace_implementation=workspace_implementation,
        additional_instructions=additional_instructions,
        instruction_body=instruction_body,
        instruction_blocks=instruction_blocks,
        include_tool_catalog=include_tool_catalog,
        include_skill_gallery=include_skill_gallery,
        skill_consumer=agent_name,
    )
    system_msg = create_cached_system_message([
        {"text": system_text, "cache": True},
    ])
    user_msg = create_cached_human_message(user_blocks)
    channels = [
        ChannelSpec(name="thinking", format="markdown", replace_citations=False, emit_marker="thinking"),
        ChannelSpec(name="ReactDecisionOutV2", format="json", model=ReactDecisionOutV2, replace_citations=False, emit_marker="answer"),
        ChannelSpec(name="code", format="text", replace_citations=False, emit_marker="subsystem"),
        ChannelSpec(name="summary", format="markdown", replace_citations=False, emit_marker="subsystem"),
    ]

    async def _emit_delta(**kwargs):
        # Never stream structured JSON channel to the main stream; it is handled via subscribers only.
        if (kwargs.get("channel") or "") in {"ReactDecisionOutV2", "code", "summary"}:
            if kwargs.get("channel") == "code":
                pass
            return
        text = kwargs.get("text") or ""
        completed = bool(kwargs.get("completed"))
        if on_progress_delta is not None:
            try:
                await on_progress_delta(**kwargs)
            except TypeError:
                await on_progress_delta(text or "", completed=completed)

    async def _emit_raw_delta(piece: str):
        if not piece or on_raw_delta is None:
            return
        try:
            await on_raw_delta(piece)
        except TypeError:
            await on_raw_delta(text=piece, completed=False)

    results, meta = await stream_with_channels(
        svc,
        messages=[system_msg, user_msg],
        role=agent_name,
        channels=channels,
        emit=_emit_delta,
        agent=agent_name,
        artifact_name="react.decision",
        sources_list=None,
        subscribers=subscribers,
        raw_emit=_emit_raw_delta,
        max_tokens=max_tokens,
        temperature=0.6,
        return_full_raw=True,
    )

    service_error = (meta or {}).get("service_error") if isinstance(meta, dict) else None
    if service_error:
        # Infra constructs ServiceError; decision only propagates it.
        if isinstance(service_error, ServiceError):
            raise ServiceException(service_error)
        if isinstance(service_error, dict):
            raise ServiceException(ServiceError.model_validate(service_error))
        raise ServiceException(ServiceError(
            kind=ServiceKind.llm,
            service_name="react.decision",
            error_type=type(service_error).__name__,
            message=str(service_error),
        ))

    res_thinking = results.get("thinking")
    res_json = results.get("ReactDecisionOutV2")
    res_code = results.get("code")
    res_summary = results.get("summary")
    thinking_raw = res_thinking.raw if res_thinking else ""
    json_raw = res_json.raw if res_json else ""
    code_raw = res_code.raw if res_code else ""
    summary_raw = res_summary.raw if res_summary else ""
    err = res_json.error if res_json else None

    data = {}
    if res_json and res_json.obj is not None:
        try:
            data = res_json.obj.model_dump()
        except Exception:
            data = res_json.obj
    ok_flag = (service_error is None) and (err is None)

    return {
        "agent_response": data,
        "log": {
            "error": err,
            "raw_data": json_raw,
            "service_error": service_error,
            "ok": ok_flag,
        },
        "raw": (meta or {}).get("raw") if isinstance(meta, dict) else None,
        "internal_thinking": thinking_raw,
        "working_summary": summary_raw,
        "channels": {
            "thinking": {
                "text": thinking_raw,
                "started_at": res_thinking.started_at if res_thinking else None,
                "finished_at": res_thinking.finished_at if res_thinking else None,
            },
            "ReactDecisionOutV2": {
                "text": json_raw,
                "started_at": res_json.started_at if res_json else None,
                "finished_at": res_json.finished_at if res_json else None,
            },
            "code": {
                "text": code_raw,
                "started_at": res_code.started_at if res_code else None,
                "finished_at": res_code.finished_at if res_code else None,
            },
            "summary": {
                "text": summary_raw,
                "started_at": res_summary.started_at if res_summary else None,
                "finished_at": res_summary.finished_at if res_summary else None,
            },
        },
    }
