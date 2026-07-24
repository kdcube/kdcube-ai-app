# URL Generation (compact)

Generate clean, human-facing URLs that are relevant and likely accessible for fetch tools when external evidence is needed.

## Tool
- `generic_tools.fetch_url_contents` — fetches content from the generated URLs for evidence gathering. Call it with your URL list once the sources are formed, e.g. `{"urls": ["https://..."]}`.

## Rules
1. Relevance
   - Only suggest URLs clearly relevant to the task.
   - Suggest deep paths only when you are sure they exist.

2. Prefer human-facing pages
   - Prefer normal, human-facing pages over programmatic endpoints.
   - If multiple paths lead to the same info, prefer the one without segments like api, v1, v2, json, rest, graphql.
   - Example: prefer https://openai.com/pricing over https://openai.com/api/pricing.

3. Machine-only endpoints on explicit request
   - Suggest /api/, .json, .xml, or /graphql only when the user explicitly asks for APIs or raw data.

## Hard Rule for fetch_context
- Generated URLs are new strings that do not yet exist in context, so they go directly into tool_call.params (e.g., {"urls": ["https://..."]}).
- fetch_context is only for reusing existing strings from context; keep fetch_context.path for those existing strings.
