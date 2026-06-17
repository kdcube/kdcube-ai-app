/** Markdown renderer (react-markdown + GFM/line-breaks), auto-closes unclosed
 *  fences, memoised. Ported from the in-tree widget; `./utils` rewired to the
 *  package UI lib. */
import { memo, useMemo } from 'react'
import ReactMarkdown from 'react-markdown'
import { closeStreamingMarkdown, markdownPlugins } from '../support/utils.ts'

function MarkdownBlockImpl({ content, compact = false }: { content: string; compact?: boolean }) {
  const normalized = useMemo(() => closeStreamingMarkdown(content), [content])

  return (
    <div className={`markdown-body ${compact ? 'text-[13px]' : 'text-[14px]'}`}>
      <ReactMarkdown
        remarkPlugins={markdownPlugins}
        components={{
          a: ({ children, href }) => (
            <a href={href} target="_blank" rel="noreferrer">
              {children}
            </a>
          ),
          p: ({ children }) => (
            <p className={compact ? 'my-1 leading-5' : 'my-2 leading-6'}>{children}</p>
          ),
          ul: ({ children }) => <ul className={compact ? 'my-1 list-disc pl-5' : 'my-2 list-disc pl-5'}>{children}</ul>,
          ol: ({ children }) => <ol className={compact ? 'my-1 list-decimal pl-5' : 'my-2 list-decimal pl-5'}>{children}</ol>,
          li: ({ children }) => <li className="my-0.5">{children}</li>,
        }}
      >
        {normalized}
      </ReactMarkdown>
    </div>
  )
}

export const MarkdownBlock = memo(MarkdownBlockImpl)
