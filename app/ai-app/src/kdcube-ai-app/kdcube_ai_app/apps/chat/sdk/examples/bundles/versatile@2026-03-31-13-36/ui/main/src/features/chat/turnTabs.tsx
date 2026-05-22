/** Tab contents used by `TurnView`:
 *
 *  - StepList ........... `Steps` tab
 *  - LinksPanel ......... `Links` tab + TurnLink type + collectTurnLinks helper
 *  - CanvasPanel ........ `Canvas` tab
 *  - ThinkingBlock ...... thinking carrier rendered above the Overview feed
 *  - TimelineFeed ....... `Timeline` tab
 *  - DownloadsPanel ..... `Files` tab
 *  - ArtifactFeed ....... per-kind renderer used by `MergedOverviewFeed`
 *  - FollowupMessageBlock interleaved follow-up bubbles
 *  - OverviewEvent + mergeOverviewEvents + MergedOverviewFeed
 *
 *  All bodies moved verbatim from App.tsx (Wave 2) — no behaviour change.
 */
import { useState } from 'react'
import {
  downloadBlobAsFile,
  downloadHostedFile,
  downloadResourceByRN,
} from '../../service.ts'
import type { StepStatus } from '../../service.ts'
import {
  formatBytes,
  formatTime,
  messageForError,
  shortUrl,
} from '../../components/utils.ts'
import { inferLanguage } from '../../components/highlight.ts'
import { MarkdownBlock } from '../../components/MarkdownBlock.tsx'
import { CaretIcon } from '../../components/CaretIcon.tsx'
import { CopyButton } from '../../components/CopyButton.tsx'
import { Snippet } from '../../components/Snippet.tsx'
import { CanvasRender } from '../../components/CanvasRender.tsx'
import type {
  AdditionalUserMessage,
  Artifact,
  CanvasArtifact,
  FileArtifact,
  TimelineEntry,
  TimelineEntryKind,
  TurnAttachment,
  TurnStep,
} from './chatTypes.ts'

export function StepList({ steps }: { steps: TurnStep[] }) {
  if (steps.length === 0) return null
  const statusChip = (status: StepStatus) => {
    switch (status) {
      case 'completed':
        return 'k-chip k-green'
      case 'error':
        return 'k-chip k-pink'
      case 'started':
        return 'k-chip k-teal'
      default:
        return 'k-chip'
    }
  }
  return (
    <div className="flex flex-col gap-1.5 pt-1">
      {steps.map((step) => {
        const hasBody = Boolean(
          step.markdown || (typeof step.data?.message === 'string') || step.error,
        )
        return (
          <div key={step.step} className="k-workitem">
            <div className="k-workitem-head">
              <span className="k-workitem-icon">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="12" cy="12" r="9" />
                  <path d="M9 12l2 2 4-4" />
                </svg>
              </span>
              <span className="k-workitem-title">
                <span className="k-text">{step.title || step.step}</span>
                <span className={statusChip(step.status)}>{step.status}</span>
                {step.agent ? <span className="k-micro">{step.agent}</span> : null}
              </span>
            </div>
            {hasBody ? (
              <div className="k-workitem-body">
                {step.markdown ? <MarkdownBlock content={step.markdown} compact /> : null}
                {!step.markdown && typeof step.data?.message === 'string' ? (
                  <p className="text-[12px] text-[var(--muted)]">{step.data.message}</p>
                ) : null}
                {step.error ? (
                  <p className="text-[12px] text-[var(--pink-dark)]">{step.error}</p>
                ) : null}
              </div>
            ) : null}
          </div>
        )
      })}
    </div>
  )
}
export interface TurnLink {
  id: string
  kind: 'citation' | 'web_search' | 'web_fetch'
  title: string
  url: string
  body?: string | null
}

/* shortUrl is now imported from ./components/utils.ts */

export function collectTurnLinks(artifacts: Artifact[]): TurnLink[] {
  const links: TurnLink[] = []
  const seen = new Set<string>()

  const addLink = (link: TurnLink) => {
    if (!link.url || seen.has(link.url)) return
    seen.add(link.url)
    links.push(link)
  }

  artifacts.forEach((artifact) => {
    if (artifact.kind === 'citation') {
      addLink({
        id: `citation:${artifact.url}`,
        kind: 'citation',
        title: artifact.title || artifact.url,
        url: artifact.url,
        body: artifact.body,
      })
    }
    if (artifact.kind === 'web_search') {
      artifact.items.forEach((item) => {
        addLink({
          id: `web-search:${item.url}`,
          kind: 'web_search',
          title: item.title || item.url,
          url: item.url,
          body: item.body,
        })
      })
    }
    if (artifact.kind === 'web_fetch') {
      artifact.items.forEach((item) => {
        addLink({
          id: `web-fetch:${item.url}`,
          kind: 'web_fetch',
          title: item.url,
          url: item.url,
          body: [
            item.status ? item.status.toUpperCase() : null,
            item.mime,
            typeof item.content_length === 'number' ? formatBytes(item.content_length) : null,
          ].filter(Boolean).join(' • '),
        })
      })
    }
  })

  return links
}

export function LinksPanel({ links }: { links: TurnLink[] }) {
  if (links.length === 0) {
    return <p className="pt-2 text-[12px] text-[var(--muted)]">No links have been produced for this turn yet.</p>
  }

  const linkChip = (kind: TurnLink['kind']) => {
    switch (kind) {
      case 'web_search':
        return 'k-chip k-teal'
      case 'web_fetch':
        return 'k-chip k-gold'
      default:
        return 'k-chip k-blue'
    }
  }

  return (
    <div className="k-result-list mt-1">
      {links.map((link) => (
        <a
          key={link.id}
          href={link.url}
          target="_blank"
          rel="noreferrer"
          className="k-result-row"
        >
          <span className="k-result-favicon" aria-hidden="true" />
          <div className="k-result-main">
            <span className="k-result-title">{link.title}</span>
            <span className="k-result-host">{shortUrl(link.url)}</span>
            {link.body ? <span className="k-result-body">{link.body}</span> : null}
          </div>
          <span className={linkChip(link.kind)}>{link.kind.replace('_', ' ')}</span>
        </a>
      ))}
    </div>
  )
}
export function CanvasPanel({ canvases }: { canvases: CanvasArtifact[] }) {
  if (canvases.length === 0) {
    return <p className="pt-2 text-[12px] text-[var(--muted)]">No canvas items in this turn yet.</p>
  }
  return (
    <div className="flex flex-col gap-2 pt-1">
      {canvases.map((canvas) => (
        <details key={`${canvas.kind}-${canvas.name}-${canvas.timestamp}`} className="k-workitem k-tint-green" open>
          <summary className="k-workitem-head">
            <span className="k-workitem-icon">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="3" y="3" width="18" height="18" rx="2" />
                <path d="M3 9h18M9 21V9" />
              </svg>
            </span>
            <span className="k-workitem-title">
              <span className="k-text">{canvas.title || canvas.name}</span>
              <span className="k-micro">{canvas.format || 'text'}</span>
            </span>
            <span className="k-workitem-meta">{formatTime(canvas.timestamp)}</span>
            <span className="k-snippet-tools" onClick={(e) => e.stopPropagation()}>
              <CopyButton value={canvas.content} title="Copy canvas" />
              <DownloadButton
                data={canvas.content}
                filename={canvasFilename(canvas)}
                mime={canvasMime(canvas)}
                title="Download canvas"
              />
            </span>
            <CaretIcon />
          </summary>
          <div className="k-workitem-body">
            <CanvasRender canvas={canvas} />
          </div>
        </details>
      ))}
    </div>
  )
}
export function ThinkingBlock({
  entries,
  active,
}: {
  entries: TimelineEntry[]
  active: boolean
}) {
  if (entries.length === 0) return null

  const sortedEntries = entries.slice().sort((left, right) => left.timestamp - right.timestamp)

  return (
    <details className={`k-workitem k-tint-gold ${active ? 'k-live' : ''}`} open={active}>
      <summary className="k-workitem-head">
        <span className="k-workitem-icon" aria-hidden="true">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M12 2v3M12 19v3M4.93 4.93l2.12 2.12M16.95 16.95l2.12 2.12M2 12h3M19 12h3M4.93 19.07l2.12-2.12M16.95 7.05l2.12-2.12" />
          </svg>
        </span>
        <span className="k-workitem-title">
          <span className="k-text">Thinking</span>
          <span className="k-micro">{sortedEntries.length} step{sortedEntries.length === 1 ? '' : 's'}</span>
        </span>
        {active ? <span className="k-status k-live" aria-label="live" /> : null}
        <CaretIcon />
      </summary>
      <div className="k-workitem-body">
        <div className="max-h-[260px] overflow-auto pr-1">
          {sortedEntries.map((entry) => (
            <div key={entry.id} className="border-l border-[var(--line-soft)] pl-3 py-1.5 text-[12px]">
              <div className="flex flex-wrap items-center gap-2 text-[var(--muted)]">
                <span className="font-medium text-[var(--ink)]">{entry.agent || entry.title}</span>
                {entry.status ? <span>{entry.status}</span> : null}
                <span className="ml-auto">{formatTime(entry.timestamp)}</span>
              </div>
              {entry.body ? (
                <div className="pt-1">
                  <MarkdownBlock content={entry.body} compact />
                </div>
              ) : (
                <p className="pt-1 text-[var(--muted)]">Reasoning started.</p>
              )}
            </div>
          ))}
        </div>
      </div>
    </details>
  )
}
export function TimelineFeed({ entries }: { entries: TimelineEntry[] }) {
  if (entries.length === 0) {
    return <p className="pt-2 text-[12px] text-[var(--muted)]">No timeline events yet.</p>
  }

  const sortedEntries = entries.slice().sort((left, right) => left.timestamp - right.timestamp)

  const chipClass = (kind: TimelineEntryKind): string => {
    switch (kind) {
      case 'answer':
        return 'k-chip k-teal'
      case 'thinking':
        return 'k-chip k-gold'
      case 'subsystem':
        return 'k-chip k-blue'
      case 'error':
        return 'k-chip k-pink'
      case 'lifecycle':
        return 'k-chip k-green'
      default:
        return 'k-chip'
    }
  }

  /* Backend frequently sets agent = title-in-caps for subsystem entries.
     If the agent string is just the title (case-insensitive) or longer than
     ~24 chars, hide it — the title already says what the entry is. */
  const visibleAgent = (entry: TimelineEntry): string | null => {
    const raw = String(entry.agent || '').trim()
    if (!raw) return null
    if (raw.length > 24) return null
    if (raw.toLowerCase() === String(entry.title || '').toLowerCase()) return null
    return raw
  }

  return (
    <div className="flex flex-col gap-1.5 pt-1">
      {sortedEntries.map((entry) => {
        const agent = visibleAgent(entry)
        const hasBody = Boolean(entry.body)
        return (
          <details key={entry.id} className="k-workitem">
            <summary className="k-workitem-head">
              <span className={chipClass(entry.kind)}>{entry.kind}</span>
              <span className="k-workitem-title">
                <span className="k-text">{entry.title}</span>
                {agent ? <span className="k-micro">{agent}</span> : null}
                {entry.status ? <span className="k-micro">{entry.status}</span> : null}
              </span>
              <span className="k-workitem-meta">{formatTime(entry.timestamp)}</span>
              <CaretIcon />
            </summary>
            <div className="k-workitem-body">
              {hasBody ? (
                <Snippet
                  content={entry.body!}
                  format={entry.format === 'json' ? 'json' : entry.format === 'code' ? 'code' : entry.format === 'markdown' ? 'markdown' : 'text'}
                  language={entry.format === 'code' ? inferLanguage(null, entry.body!) : undefined}
                  maxHeight={240}
                />
              ) : (
                <p className="text-[12px] text-[var(--muted)]">No body payload.</p>
              )}
            </div>
          </details>
        )
      })}
    </div>
  )
}
export function DownloadsPanel({
  attachments,
  files,
  onError,
}: {
  attachments: TurnAttachment[]
  files: FileArtifact[]
  onError: (text: string) => void
}) {
  const [downloadingId, setDownloadingId] = useState<string | null>(null)

  if (attachments.length === 0 && files.length === 0) {
    return <p className="pt-2 text-[12px] text-[var(--muted)]">No downloadable files for this turn yet.</p>
  }

  const handleAttachmentDownload = async (attachment: TurnAttachment, index: number) => {
    try {
      setDownloadingId(`attachment:${index}`)
      if (attachment.file) {
        downloadBlobAsFile(attachment.file, attachment.name)
        return
      }
      if (attachment.rn) {
        await downloadResourceByRN(attachment.rn, attachment.name)
        return
      }
      if (attachment.hostedUri) {
        await downloadHostedFile(attachment.hostedUri, attachment.name)
        return
      }
      throw new Error('Attachment download metadata is missing.')
    } catch (error) {
      onError(messageForError(error))
    } finally {
      setDownloadingId(null)
    }
  }

  const handleFileDownload = async (file: FileArtifact) => {
    try {
      setDownloadingId(`file:${file.rn}`)
      await downloadResourceByRN(file.rn, file.filename)
    } catch (error) {
      onError(messageForError(error))
    } finally {
      setDownloadingId(null)
    }
  }

  return (
    <div className="flex flex-col gap-3 pt-1">
      {attachments.length > 0 ? (
        <div>
          <div className="k-micro pb-1">Sent attachments</div>
          <div className="k-result-list">
            {attachments.map((attachment, index) => (
              <button
                key={attachment.id}
                type="button"
                onClick={() => void handleAttachmentDownload(attachment, index)}
                className="k-result-row"
                style={{ background: 'transparent', border: 0, font: 'inherit' }}
              >
                <span className="k-workitem-icon" style={{ width: 18, height: 18 }}>
                  <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M21.4 11.05 12.5 19.95a5 5 0 1 1-7-7l9-9a3.5 3.5 0 1 1 5 5l-9 9a2 2 0 1 1-3-3l8.5-8.5" />
                  </svg>
                </span>
                <div className="k-result-main">
                  <span className="k-result-title">{attachment.name}</span>
                  <span className="k-result-host">
                    {typeof attachment.size === 'number' ? formatBytes(attachment.size) : attachment.mime || attachment.rn || 'Stored attachment'}
                  </span>
                </div>
                <span className="text-[12px] text-[var(--blue-dark)]">
                  {downloadingId === `attachment:${index}` ? 'Preparing…' : 'Download'}
                </span>
              </button>
            ))}
          </div>
        </div>
      ) : null}

      {files.length > 0 ? (
        <div>
          <div className="k-micro pb-1">Assistant files</div>
          <div className="k-result-list">
            {files.map((file) => (
              <button
                key={file.rn}
                type="button"
                onClick={() => void handleFileDownload(file)}
                className="k-result-row"
                style={{ background: 'transparent', border: 0, font: 'inherit' }}
              >
                <span className="k-workitem-icon" style={{ width: 18, height: 18 }}>
                  <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                    <path d="M14 2v6h6" />
                  </svg>
                </span>
                <div className="k-result-main">
                  <span className="k-result-title">{file.filename}</span>
                  <span className="k-result-host">{file.description || file.mime || file.rn}</span>
                </div>
                <span className="text-[12px] text-[var(--blue-dark)]">
                  {downloadingId === `file:${file.rn}` ? 'Downloading…' : 'Download'}
                </span>
              </button>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  )
}
export function ArtifactFeed({ artifacts }: { artifacts: Artifact[] }) {
  if (artifacts.length === 0) return null

  const sortedArtifacts = artifacts.slice().sort((left, right) => left.timestamp - right.timestamp)

  return (
    <div className="flex flex-col gap-2 pt-1">
      {sortedArtifacts.map((artifact) => {
        if (artifact.kind === 'timeline') {
          return (
            <details key={`${artifact.kind}-${artifact.name}`} className="k-workitem k-tint-teal k-live" open>
              <summary className="k-workitem-head">
                <span className="k-workitem-icon">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <circle cx="12" cy="12" r="9" />
                    <path d="M12 7v6l4 2" />
                  </svg>
                </span>
                <span className="k-workitem-title">
                  <span className="k-text">{artifact.name}</span>
                  <span className="k-micro">live update</span>
                </span>
                <span className="k-workitem-meta">{formatTime(artifact.timestamp)}</span>
                <CaretIcon />
              </summary>
              <div className="k-workitem-body">
                <div className="max-h-[320px] overflow-auto pr-1">
                  <MarkdownBlock content={artifact.markdown} compact />
                </div>
              </div>
            </details>
          )
        }

        if (artifact.kind === 'canvas') {
          return (
            <details key={`${artifact.kind}-${artifact.name}`} className="k-workitem k-tint-green" open>
              <summary className="k-workitem-head">
                <span className="k-workitem-icon">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <rect x="3" y="3" width="18" height="18" rx="2" />
                    <path d="M3 9h18M9 21V9" />
                  </svg>
                </span>
                <span className="k-workitem-title">
                  <span className="k-text">{artifact.title || artifact.name}</span>
                  <span className="k-micro">{artifact.format || 'text'}</span>
                </span>
                <CaretIcon />
              </summary>
              <div className="k-workitem-body">
                <CanvasRender canvas={artifact} />
              </div>
            </details>
          )
        }

        if (artifact.kind === 'citation') {
          return (
            <a
              key={`${artifact.kind}-${artifact.url}`}
              href={artifact.url}
              target="_blank"
              rel="noreferrer"
              className="k-workitem"
              style={{ display: 'block', textDecoration: 'none', color: 'inherit' }}
            >
              <div className="k-workitem-head">
                <span className="k-workitem-icon">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M10 13a5 5 0 0 0 7.07 0l3-3a5 5 0 1 0-7.07-7.07L11.5 4.5" />
                    <path d="M14 11a5 5 0 0 0-7.07 0l-3 3a5 5 0 0 0 7.07 7.07l1.5-1.5" />
                  </svg>
                </span>
                <span className="k-workitem-title">
                  <span className="k-text">{artifact.title || artifact.url}</span>
                </span>
                <span className="k-workitem-meta">{shortUrl(artifact.url)}</span>
              </div>
              {artifact.body ? (
                <div className="k-workitem-body">
                  <div className="line-clamp-2 text-[12px] text-[var(--text-2)]">{artifact.body}</div>
                </div>
              ) : null}
            </a>
          )
        }

        if (artifact.kind === 'file') {
          return (
            <div key={`${artifact.kind}-${artifact.rn}`} className="k-workitem">
              <div className="k-workitem-head">
                <span className="k-workitem-icon">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                    <path d="M14 2v6h6" />
                  </svg>
                </span>
                <span className="k-workitem-title">
                  <span className="k-text">{artifact.filename}</span>
                  <span className="k-micro">file</span>
                </span>
                <span className="k-workitem-meta">
                  {artifact.description || artifact.mime || (artifact.rn ? artifact.rn.split(':').pop() : '')}
                </span>
              </div>
            </div>
          )
        }

        if (artifact.kind === 'web_search') {
          return (
            <details key={`${artifact.kind}-${artifact.searchId}`} className="k-workitem k-tint-sky" open>
              <summary className="k-workitem-head">
                <span className="k-workitem-icon">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <circle cx="11" cy="11" r="7" />
                    <path d="M21 21l-4.3-4.3" />
                  </svg>
                </span>
                <span className="k-workitem-title">
                  <span className="k-text">{artifact.title || artifact.name || 'Web search'}</span>
                  <span className="k-micro">
                    web search · {artifact.items.length} result{artifact.items.length === 1 ? '' : 's'}
                  </span>
                </span>
                <span className="k-workitem-meta">{formatTime(artifact.timestamp)}</span>
                <CaretIcon />
              </summary>
              <div className="k-workitem-body">
                {artifact.objective ? (
                  <p className="text-[12px] text-[var(--muted)]">{artifact.objective}</p>
                ) : null}
                {artifact.queries.length > 0 ? (
                  <div className="k-query-row">
                    <span className="k-micro">queries</span>
                    {artifact.queries.map((query) => (
                      <span key={query} className="k-query-chip">{query}</span>
                    ))}
                  </div>
                ) : null}
                {artifact.items.length > 0 ? (
                  <div className="k-result-list">
                    {artifact.items.slice(0, 6).map((item, idx) => (
                      <a
                        key={item.url}
                        href={item.url}
                        target="_blank"
                        rel="noreferrer"
                        className="k-result-row"
                      >
                        <span className="k-result-favicon" aria-hidden="true" />
                        <div className="k-result-main">
                          <span className="k-result-title">{item.title || shortUrl(item.url)}</span>
                          <span className="k-result-host">{shortUrl(item.url)}</span>
                          {item.body ? <span className="k-result-body">{item.body}</span> : null}
                        </div>
                        <span className="k-result-tag">[{idx + 1}]</span>
                      </a>
                    ))}
                  </div>
                ) : null}
                {artifact.reportContent ? (
                  <details>
                    <summary className="cursor-pointer text-[12px] font-medium text-[var(--blue-dark)]">
                      Show report
                    </summary>
                    <div className="mt-1 max-h-[360px] overflow-auto pr-1">
                      <MarkdownBlock content={artifact.reportContent} compact />
                    </div>
                  </details>
                ) : null}
              </div>
            </details>
          )
        }

        if (artifact.kind === 'web_fetch') {
          return (
            <details key={`${artifact.kind}-${artifact.executionId}`} className="k-workitem k-tint-gold" open>
              <summary className="k-workitem-head">
                <span className="k-workitem-icon">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M21 12a9 9 0 1 1-9-9" />
                    <path d="M21 3v6h-6" />
                  </svg>
                </span>
                <span className="k-workitem-title">
                  <span className="k-text">{artifact.title || artifact.name || 'Web fetch'}</span>
                  <span className="k-micro">
                    web fetch · {artifact.items.length} URL{artifact.items.length === 1 ? '' : 's'}
                  </span>
                </span>
                <span className="k-workitem-meta">{formatTime(artifact.timestamp)}</span>
                <CaretIcon />
              </summary>
              <div className="k-workitem-body">
                <div className="k-result-list">
                  {artifact.items.slice(0, 6).map((item) => (
                    <a
                      key={item.url}
                      href={item.url}
                      target="_blank"
                      rel="noreferrer"
                      className="k-result-row"
                    >
                      <span className="k-result-favicon" aria-hidden="true" />
                      <div className="k-result-main">
                        <span className="k-result-title">{shortUrl(item.url)}</span>
                        <span className="k-result-host">
                          {(item.status || 'unknown').toUpperCase()}
                          {item.mime ? ` · ${item.mime}` : ''}
                          {typeof item.content_length === 'number' ? ` · ${formatBytes(item.content_length)}` : ''}
                        </span>
                      </div>
                    </a>
                  ))}
                </div>
              </div>
            </details>
          )
        }

        if (artifact.kind === 'code_exec') {
          const statusLabel =
            artifact.status?.status === 'error'
              ? 'Error'
              : artifact.status?.status === 'exec'
                ? 'Executing'
                : artifact.status?.status === 'gen'
                  ? 'Generating'
                  : artifact.status?.status === 'done'
                    ? 'Done'
                    : 'Ready'
          const isError = artifact.status?.status === 'error'
          const isRunning = artifact.status?.status === 'exec' || artifact.status?.status === 'gen'
          const lang = inferLanguage(null, artifact.program || '')

          return (
            <details
              key={`${artifact.kind}-${artifact.executionId}`}
              className={`k-workitem k-tint-purple ${isError ? 'k-err' : isRunning ? 'k-live' : ''}`}
              open
            >
              <summary className="k-workitem-head">
                <span className="k-workitem-icon">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <polyline points="16 18 22 12 16 6" />
                    <polyline points="8 6 2 12 8 18" />
                  </svg>
                </span>
                <span className="k-workitem-title">
                  <span className="k-text">{artifact.title || artifact.name || 'Program'}</span>
                  <span className="k-micro">exec · {statusLabel.toLowerCase()}</span>
                </span>
                <span className="k-workitem-meta">{formatTime(artifact.timestamp)}</span>
                <CaretIcon />
              </summary>
              <div className="k-workitem-body">
                {artifact.objective ? (
                  <p className="text-[12px] text-[var(--muted)]">{artifact.objective}</p>
                ) : null}
                {artifact.contract && artifact.contract.length > 0 ? (
                  <div className="k-result-list">
                    {artifact.contract.map((item) => (
                      <div key={item.filename} className="k-result-row" style={{ gridTemplateColumns: 'auto minmax(0,1fr)' }}>
                        <span className="k-workitem-icon" style={{ width: 18, height: 18 }}>
                          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                            <path d="M14 2v6h6" />
                          </svg>
                        </span>
                        <div className="k-result-main">
                          <span className="k-result-title">{item.filename}</span>
                          {item.description ? <span className="k-result-host">{item.description}</span> : null}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : null}
                {artifact.program ? (
                  <Snippet
                    content={artifact.program}
                    format="code"
                    language={lang}
                    label={lang}
                    filename={`program.${lang === 'python' ? 'py' : lang === 'javascript' ? 'js' : lang === 'bash' ? 'sh' : 'txt'}`}
                    downloadMime="text/plain"
                    showDownload
                  />
                ) : null}
                {artifact.status?.status === 'error' && artifact.status.error ? (
                  <div className="k-notice k-error">
                    <span>{Object.values(artifact.status.error).join(' ')}</span>
                  </div>
                ) : null}
              </div>
            </details>
          )
        }

        return (
          <div key={`${artifact.kind}-${artifact.timestamp}`} className="k-notice k-error">
            <span>{artifact.message}</span>
          </div>
        )
      })}
    </div>
  )
}
export function FollowupMessageBlock({ message }: { message: AdditionalUserMessage }) {
  const isSteer = message.continuationKind === 'steer'
  const text = message.text || (isSteer ? 'Stop requested' : '')
  return (
    <div className="flex flex-col gap-1 self-end max-w-[760px]" style={{ marginLeft: 'auto' }}>
      <div className="flex items-center gap-2 text-[11px] text-[var(--muted)]">
        <span className={`k-chip ${isSteer ? 'k-pink' : 'k-teal'}`}>
          {isSteer ? 'steer' : 'follow-up'}
        </span>
        <span>{formatTime(message.timestamp)}</span>
      </div>
      <div className="k-msg rounded-md border border-[var(--line-soft)] bg-[var(--surface-2)] px-3 py-2 text-[14px] leading-6 whitespace-pre-wrap">
        {text}
        {text ? (
          <span className="k-msg-toolbar">
            <CopyButton value={text} title="Copy follow-up" />
          </span>
        ) : null}
        {message.attachments.length > 0 ? (
          <div className="flex flex-wrap gap-1.5 pt-1.5">
            {message.attachments.map((attachment) => (
              <span key={attachment.id} className="k-chip">
                {attachment.name}
                {typeof attachment.size === 'number' ? ` · ${formatBytes(attachment.size)}` : ''}
              </span>
            ))}
          </div>
        ) : null}
      </div>
    </div>
  )
}

export type OverviewEvent =
  | { kind: 'artifact'; timestamp: number; artifact: Artifact; key: string }
  | { kind: 'followup'; timestamp: number; message: AdditionalUserMessage; key: string }

export function mergeOverviewEvents(
  artifacts: Artifact[],
  additionalUserMessages: AdditionalUserMessage[],
): OverviewEvent[] {
  const events: OverviewEvent[] = []
  artifacts.forEach((artifact, index) => {
    events.push({
      kind: 'artifact',
      timestamp: artifact.timestamp,
      artifact,
      key: `artifact:${artifact.kind}:${index}:${artifact.timestamp}`,
    })
  })
  additionalUserMessages.forEach((message) => {
    events.push({
      kind: 'followup',
      timestamp: message.timestamp,
      message,
      key: `followup:${message.id}`,
    })
  })
  events.sort((left, right) => left.timestamp - right.timestamp)
  return events
}

export function MergedOverviewFeed({
  events,
}: {
  events: OverviewEvent[]
}) {
  if (events.length === 0) return null
  /* Each artifact pass goes through ArtifactFeed with a one-element list so
     we reuse its existing per-kind rendering without duplicating logic. */
  return (
    <div className="flex flex-col gap-2 pt-1">
      {events.map((event) => {
        if (event.kind === 'followup') {
          return <FollowupMessageBlock key={event.key} message={event.message} />
        }
        return <ArtifactFeed key={event.key} artifacts={[event.artifact]} />
      })}
    </div>
  )
}
