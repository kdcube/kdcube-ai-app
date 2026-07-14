/**
 * Rail / titlebar icons — the same stroke glyphs the shared scene host uses, so
 * this scene reads identically to the others. Two chat surfaces: a research chat
 * and a tool-agent chat.
 */

import React from 'react'

function StrokeSvg({ children }: { children: React.ReactNode }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {children}
    </svg>
  )
}

/** Research chat — a chat bubble over a magnifier. */
export function ResearchChatIcon() {
  return (
    <StrokeSvg>
      <path d="M21 11.5a8.4 8.4 0 0 1-9 8 9 9 0 0 1-4-1L3 20l1.5-4.5A8.4 8.4 0 0 1 12 3a8.4 8.4 0 0 1 9 8.5z" />
      <circle cx="11" cy="11" r="2.4" />
      <path d="m13.1 13.1 1.9 1.9" />
    </StrokeSvg>
  )
}

/** Tool-agent chat — a chat bubble marked with a wrench. */
export function ToolChatIcon() {
  return (
    <StrokeSvg>
      <path d="M21 11.5a8.4 8.4 0 0 1-9 8 9 9 0 0 1-4-1L3 20l1.5-4.5A8.4 8.4 0 0 1 12 3a8.4 8.4 0 0 1 9 8.5z" />
      <path d="M14.2 8.2a2 2 0 0 0-2.7 2.4l-2.4 2.4 1.3 1.3 2.4-2.4a2 2 0 0 0 2.4-2.7l-1.1 1.1-1-.2-.2-1z" />
    </StrokeSvg>
  )
}

const ICONS: Record<string, () => React.JSX.Element> = {
  chat_lg_solution: ResearchChatIcon,
  chat_lg_react: ToolChatIcon,
}

export function componentIcon(alias: string): React.JSX.Element {
  const Icon = ICONS[alias] ?? ResearchChatIcon
  return <Icon />
}
