# Recipe: Canvas Pinboard

The canvas pinboard is an app widget that materializes object references as spatial pins. It is a context target for almost every namespace and a context source when the user drags pins back to other widgets.

Read [Architecture Of What You Build](../../arch/architecture-of-what-you-build-README.md)
first for the app/service-provider map. This recipe covers only the Pinboard
surface.

## Runtime Shape

```text
pinboard iframe
  board state
    board id
    pins
    positions
  namespace presentation
    color/icon by provider namespace or scoped object kind
    label by object metadata
  drag adapter
    context drag start/end
    local pin movement
  backend API
    pin create/update/delete
    search
    object action routing
```

## Scene Boundary

The scene decides where cross-surface drops go. The pinboard decides how pins are stored and moved inside the board.

```text
context dropped on pinboard
  scene -> kdcube.surface.command target_surface=sdk.canvas.pinboard action=pin
  pinboard -> create pin for object_ref

pin dragged from pinboard
  pinboard -> kdcube-context-drag-start
  scene -> highlight matching targets
  scene -> attach/open/pin based on drop target
```

## Namespace Styling

Pin color/icon is provider-owned presentation. The pinboard should consume the
same namespace presentation config as chat and scene overlays:

```text
object_ref = task:issue:...
presentation key = task or task:issue
namespace presentation -> color/icon
pin rendering -> configured presentation
scene overlay -> same configured presentation
chat chip -> same configured presentation
```

Canvas-specific fallback colors hide configuration bugs. Missing presentation
config should be visible in logs.

## Config

```json
{
  "contextDropTargets": {
    "pinboard": {
      "surfaceRef": "website.pinboard",
      "accepts": "context",
      "dropEffect": "pin",
      "targetSurface": "sdk.canvas.pinboard",
      "action": "pin"
    }
  }
}
```

## Event And Data Bus

Pinboard board changes are naturally Data Bus events because they are state patches. Search and embedding economics produce accounting events through the Event Bus.

The widget can run standalone by opening its own runtime connections. In a scene, live delivery should become a declared transport choice:

```json
{
  "widgetConfig": {
    "pinboard": {
      "liveEventsTransport": "scene",
      "dataBusTransport": "scene"
    }
  }
}
```

## Current Gaps

- Data Bus relaying by the scene is not yet as complete as Event Bus relaying.
- Pinboard actions must stay resolver-backed. The board stores proxy cards and
  never decides behavior from provider URI grammar.

## Related Docs

- [Architecture Of What You Build](../../arch/architecture-of-what-you-build-README.md)
- [Component Recipes](./README.md)
- [Components Ecosystem Architecture](../../sdk/solutions/ecosystem-component/components-ecosystem-README.md)
- [Canvas SDK Solution](../../sdk/solutions/canvas/canvas-sdk-solution-README.md)
- [Canvas Module Guide](../../sdk/solutions/canvas/canvas-module-guide-README.md)
- [Pin Integration](../../sdk/solutions/canvas/pin-integration-README.md)
- [Canvas Search Operations](../../sdk/solutions/canvas/search-operations-README.md)
- [Context Drag And Canvas Ingress](../../sdk/npm/components-core/context-drag-README.md)
