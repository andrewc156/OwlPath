import type { Program } from '../data/types'

type Props = { programs: Program[]; value: string; onChange: (id: string) => void }

export function MajorPicker({ programs, value, onChange }: Props) {
  return (
    <label className="major-picker">
      Major{' '}
      <select value={value} onChange={(e) => onChange(e.target.value)}>
        {programs.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
      </select>
    </label>
  )
}
