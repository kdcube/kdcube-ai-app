---
title: Versatile Scene SDK Components
kind: design-note
bundle_id: versatile@2026-03-31-13-36
updated_at: 2026-06-09
---

# Versatile Scene SDK Components

The active main view is `ui/scene`. It is a host scene for reusable SDK
components, not a second custom chat implementation.

```text
ui/scene
  |
  +-- iframe: widgets/versatile_chat
  |     source: sdk://solutions/chat/ui/widget
  |
  +-- iframe: widgets/memories
  |     source: sdk://context/memory/ui/widget/memories
  |
  +-- React component: CanvasBoard
        source: sdk://solutions/canvas/ui/component
```

## Backend Surfaces

The scene uses bundle operations for request/response APIs:

| Operation | Purpose |
| --- | --- |
| `canvas_list` | List the current user's canvases for the scene story. |
| `canvas_read` | Read one canvas projection. |
| `canvas_attachment_upload` | Host local dropped files as canvas-owned attachments. |
| `canvas_object_action` | Call the resolver for a pinned object's namespace. |

Canvas mutations are published over Data Bus:

| Subject | Partition | Purpose |
| --- | --- | --- |
| `canvas.patch` | `object_ref` | Ordered canvas revision writes. |

Use generic canvas names. Do not prefix them with this bundle id. The scene is
demonstrating a reusable SDK component, so the protocol names are `canvas.*`.

## Chat Context Wiring

The scene tells the chat widget which event-source ids to use:

| Query Param | Value |
| --- | --- |
| `chat_canvas_state_event_source_id` | `canvas.state` |
| `chat_canvas_focus_event_source_id` | `canvas.focus` |
| `chat_canvas_surface` | `canvas` |
| `chat_canvas_ingress_message` | `kdcube-canvas-ingress` |
| `chat_canvas_patch_step` | `canvas.patch` |

When the user attaches the whole board, the scene sends
`kdcube-context-attach` to the chat widget. When the user attaches cards, the
scene sends `kdcube-context-focus`.

Dragging a card from canvas to chat always passes the proxied object context
(`task:`, `mem:`, `fi:`, `cnv:`, etc.). If the user also attaches the whole
canvas, the timeline receives both the canvas state event and the focused
object events.

## Memory Widget Wiring

The memory widget remains the owner of memory UI behavior. The scene only
mounts the iframe and forwards context messages from the memory widget to chat.

```text
memory widget drag
  -> kdcube-context-focus / kdcube-context-attach
  -> scene broker
  -> versatile_chat iframe
```

The compact view is the default. The scene can enlarge it through
`kdcube-set-view` with `widget=memories`.

## Canvas Object Resolvers

The backend registers resolvers for namespaces the scene can display:

| Namespace | Owner |
| --- | --- |
| `fi:` | ReAct event/artifact resolver |
| `mem:` | memory subsystem resolver |
| `cnv:` | canvas-owned object resolver |

The canvas card stores one canonical object ref. The resolver owns preview,
download, open, and rehost behavior.
