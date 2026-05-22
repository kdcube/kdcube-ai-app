/** Inline notice strip for transient banners. Moved verbatim from App.tsx (Wave 2). */
import type { BannerTone } from '../../service.ts'
import type { Banner } from '../chat/chatTypes.ts'

export function BannerStrip({
  banners,
  onDismiss,
}: {
  banners: Banner[]
  onDismiss: (id: string) => void
}) {
  if (banners.length === 0) return null
  const noticeClass = (tone: BannerTone) => {
    switch (tone) {
      case 'error':
        return 'k-notice k-error'
      case 'warning':
        return 'k-notice k-warning'
      case 'success':
        return 'k-notice k-success'
      default:
        return 'k-notice k-info'
    }
  }
  return (
    <div className="flex flex-col gap-2">
      {banners.map((banner) => (
        <div key={banner.id} className={noticeClass(banner.tone)}>
          <div className="min-w-0 flex-1">{banner.text}</div>
          <button
            type="button"
            className="k-iconbtn k-borderless"
            onClick={() => onDismiss(banner.id)}
            aria-label="Dismiss"
            title="Dismiss"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M18 6L6 18M6 6l12 12" />
            </svg>
          </button>
        </div>
      ))}
    </div>
  )
}
