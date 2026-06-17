/** Inline followup chip row. Ported verbatim from the in-tree widget. */
export function SuggestedQuestions({
  items,
  disabled,
  onSelect,
}: {
  items: string[]
  disabled: boolean
  onSelect: (text: string) => void
}) {
  if (items.length === 0) return null
  return (
    <div className="flex flex-wrap gap-1.5 pt-2">
      {items.map((item) => (
        <button
          key={item}
          type="button"
          disabled={disabled}
          onClick={() => onSelect(item)}
          className="k-followup"
        >
          {item}
        </button>
      ))}
    </div>
  )
}
