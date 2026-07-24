/**
 * The composition-token palette the editor offers. Convenience only — the
 * server accepts any token in the composer vocabulary, and the AUTHORITATIVE
 * block registry lives server-side (`shared_instructions_lite.py` /
 * `instructions_extra_lite.py`; purposes are documented in the signal table of
 * `docs/sdk/agents/react/system-instruction-README.md`). A token missing here
 * can always be typed as a plain item.
 */

export interface PaletteGroup {
  label: string
  tokens: string[]
}

const LITE_PROFILES = ['core', 'workspace', 'workspace_exec', 'document', 'web', 'all_capabilities']

export const PALETTE: PaletteGroup[] = [
  {
    label: 'Predefined sets',
    tokens: ['instr:profile:full', 'instr:profile:lite', 'instr:profile:extra-lite'],
  },
  {
    label: 'Moderate profiles (lite:)',
    tokens: LITE_PROFILES.map((p) => `lite:${p}`),
  },
  {
    label: 'Extra-lite profiles (xlite:)',
    tokens: LITE_PROFILES.map((p) => `xlite:${p}`),
  },
  {
    label: 'Moderate blocks',
    tokens: [
      'REACT_LITE_IDENTITY',
      'REACT_LITE_SECURITY_GUARD',
      'REACT_LITE_TIMELINE_CONTEXT',
      'REACT_LITE_ANNOUNCE',
      'REACT_LITE_EXTERNAL_EVENTS',
      'REACT_LITE_DECISION_LOOP',
      'REACT_LITE_TOOL_USE_BASE',
      'REACT_LITE_USER_BOUNDARIES_AND_FAILURES',
      'REACT_LITE_SKILLS',
      'REACT_LITE_ATTACHMENTS',
      'REACT_LITE_SOURCES_CITATIONS',
      'REACT_LITE_PATHS_AND_NAMESPACES',
      'REACT_LITE_REACT_READ_RECOVERY',
      'REACT_LITE_WORKSPACE_BASE',
      'REACT_LITE_PROJECTS_AND_FILES',
      'REACT_LITE_SUGGESTED_FOLLOWUPS',
      'REACT_LITE_FINALIZATION',
      'REACT_LITE_REACT_WRITE_ARTIFACTS',
      'REACT_LITE_MEMORY_SEARCH_RECOVERY',
      'REACT_LITE_LOCAL_ARTIFACT_SEARCH',
      'REACT_LITE_WORKSPACE_PULL_CHECKOUT',
      'REACT_LITE_PATCHING',
      'REACT_LITE_EXEC_TOOL',
      'REACT_LITE_RENDERING_TOOLS',
      'REACT_LITE_WEB_TOOLS',
      'REACT_LITE_INTERNAL_NOTES',
      'REACT_LITE_DURABLE_USER_MEMORY_READ',
      'REACT_LITE_DURABLE_USER_MEMORY_WRITE',
      'REACT_LITE_PLANNING',
    ],
  },
]
