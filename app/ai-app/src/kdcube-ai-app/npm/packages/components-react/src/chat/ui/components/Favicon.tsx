/** FaviconImg + resolveFavicon — site mark for result rows. Prefers the
 *  artifact favicon, falls back to Google S2 by hostname; broken images hide
 *  themselves. Ported verbatim from the in-tree widget. */
export function resolveFavicon(item: { favicon?: string | null; url?: string }): string | null {
  const explicit = (item.favicon || '').trim()
  if (explicit) return explicit
  const url = (item.url || '').trim()
  if (!url) return null
  try {
    const host = new URL(url).hostname
    if (!host) return null
    return `https://www.google.com/s2/favicons?domain=${encodeURIComponent(host)}&sz=32`
  } catch {
    return null
  }
}

export function FaviconImg({ url, favicon }: { url?: string; favicon?: string | null }) {
  const src = resolveFavicon({ url, favicon })
  if (!src) return <span className="k-result-favicon" aria-hidden="true" />
  return (
    <img
      className="k-result-favicon"
      src={src}
      alt=""
      width={16}
      height={16}
      loading="lazy"
      decoding="async"
      referrerPolicy="no-referrer"
      onError={(event) => {
        (event.currentTarget as HTMLImageElement).style.visibility = 'hidden'
      }}
    />
  )
}
