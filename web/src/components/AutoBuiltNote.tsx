import { autoBuiltText } from './stateLabels'

export function AutoBuiltNote({ checked }: { checked: boolean }) {
  const text = autoBuiltText(checked)
  return text && <p className="auto-built-note" role="note">{text}</p>
}
