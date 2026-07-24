/**
 * @kdcube/components-react/agentic-config — the agentic configuration admin
 * surface as reusable components: the instruction constructor (block library
 * with signals, segmented composed rendering, versioned sets, Assign), the
 * per-app Agents editor (YAML), and App settings (YAML/JSON merge patches +
 * secrets). Host-agnostic via AgenticConfigTransport.
 */
export {
  createAgenticConfigApi,
  type AgentSlot,
  type AgenticConfigApi,
  type AgenticConfigTransport,
  type AppEntry,
  type AssignSource,
  type BuiltinBlock,
  type ComposedSegment,
  type InstructionRecord,
} from './api.ts'
export { AgenticConfigProvider, AgenticConfigTabs } from './views.tsx'
