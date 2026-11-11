import { askAndReset } from '../logic/programView'

type Props = { disabled: boolean; onReset: () => void; confirm?: (text: string) => boolean }

export function ResetButton({ disabled, onReset, confirm = (t) => window.confirm(t) }: Props) {
  return (
    <button type="button" className="reset-button" disabled={disabled} onClick={() => askAndReset(confirm, onReset)}
      title={disabled ? 'No courses are marked yet' : 'Mark every course as not taken'}>
      Reset progress
    </button>
  )
}
