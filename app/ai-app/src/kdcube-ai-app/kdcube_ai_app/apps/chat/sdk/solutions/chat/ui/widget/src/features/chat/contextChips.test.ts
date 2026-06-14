import { messageWithContextChips, splitContextChips } from './contextChips'

function assertEqual(actual: unknown, expected: unknown, label: string): void {
  if (actual !== expected) {
    throw new Error(`${label}\nactual: ${String(actual)}\nexpected: ${String(expected)}`)
  }
}

const why = { id: 'intent:landing/why-kdcube', label: 'Why', kind: 'intent' }
const encoded = JSON.stringify({ context: [why] })
const encodedPythonStyle = '{"context": [{"id": "intent:landing/why-kdcube", "label": "Why", "kind": "intent"}]}'

{
  const parsed = splitContextChips(encoded)
  assertEqual(parsed.text, '', 'bare context payload has no visible text')
  assertEqual(parsed.contexts.length, 1, 'bare context payload yields one chip')
  assertEqual(parsed.contexts[0].label, 'Why', 'bare context payload keeps label')
}

{
  const parsed = splitContextChips(`\n\n${encoded}`)
  assertEqual(parsed.text, '', 'leading-delimited context payload has no visible text')
  assertEqual(parsed.contexts.length, 1, 'leading-delimited context payload yields one chip')
}

{
  const parsed = splitContextChips(encodedPythonStyle)
  assertEqual(parsed.text, '', 'python-style context payload has no visible text')
  assertEqual(parsed.contexts.length, 1, 'python-style context payload yields one chip')
  assertEqual(parsed.contexts[0].label, 'Why', 'python-style context payload keeps label')
}

{
  const parsed = splitContextChips(`${encoded}\n\n${encoded}`)
  assertEqual(parsed.text, '', 'doubled context payload has no visible text')
  assertEqual(parsed.contexts.length, 1, 'doubled context payload dedupes chips')
}

{
  const parsed = splitContextChips(`Explain this\n\n${encoded}`)
  assertEqual(parsed.text, 'Explain this', 'text plus context preserves text')
  assertEqual(parsed.contexts.length, 1, 'text plus context yields chip')
}

{
  const rendered = messageWithContextChips(encoded, [why])
  const parsed = splitContextChips(rendered)
  assertEqual(parsed.text, '', 'message formatter strips existing context marker from visible text')
  assertEqual(parsed.contexts.length, 1, 'message formatter dedupes existing context marker and contexts')
}
