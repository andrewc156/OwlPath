import { useId, useMemo, useState } from 'react'
import type { MajorEntry } from '../data/dataset'
import { groupMajors } from '../logic/majorSearch'

type Props = { majors: MajorEntry[]; value: string; onChange: (id: string) => void }

/** A combobox: type to filter, ↑/↓ to move, Enter to choose, Escape to close. */
export function MajorPicker({ majors, value, onChange }: Props) {
  const uid = useId()
  const listId = `${uid}-list`
  const current = majors.find((m) => m.id === value)
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(0)

  const groups = useMemo(() => groupMajors(majors, query), [majors, query])
  const flat = groups.flatMap((g) => g.items)
  const optionId = (id: string) => `${uid}-opt-${id}`

  const close = () => { setOpen(false); setQuery('') }
  const choose = (id: string) => { close(); if (id !== value) onChange(id) }
  const show = () => {
    if (open) return
    setOpen(true)
    setActive(Math.max(0, groupMajors(majors, '').flatMap((g) => g.items).findIndex((m) => m.id === value)))
  }
  const move = (delta: number) => {
    show()
    if (flat.length > 0) setActive((i) => (Math.min(i, flat.length - 1) + delta + flat.length) % flat.length)
  }

  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); move(1) }
    else if (e.key === 'ArrowUp') { e.preventDefault(); move(-1) }
    else if (e.key === 'Enter' && open && flat[active]) { e.preventDefault(); choose(flat[active].id) }
    else if (e.key === 'Escape' && open) { e.preventDefault(); close() }
  }

  return (
    <div className="major-picker">
      <label htmlFor={`${uid}-input`}>Major</label>
      <input id={`${uid}-input`} type="text" role="combobox" autoComplete="off" spellCheck={false}
        aria-expanded={open} aria-controls={open ? listId : undefined} aria-autocomplete="list"
        aria-activedescendant={open && flat[active] ? optionId(flat[active].id) : undefined}
        placeholder="Search majors"
        value={open ? query : current?.name ?? ''}
        onFocus={(e) => { show(); e.currentTarget.select() }}
        onClick={show}
        onChange={(e) => { setOpen(true); setQuery(e.target.value); setActive(0) }}
        onBlur={close} onKeyDown={onKeyDown} />
      {open && (
        <div id={listId} role="listbox" aria-label="Majors" className="major-list">
          {groups.length === 0 && <div className="major-empty">No majors match.</div>}
          {groups.map((g) => (
            <div key={g.label} role="group" aria-labelledby={`${uid}-g-${g.label}`}>
              <div id={`${uid}-g-${g.label}`} className="major-group">{g.label}</div>
              {g.items.map((m) => (
                <div key={m.id} id={optionId(m.id)} role="option" aria-selected={m.id === value}
                  className={`major-option${m === flat[active] ? ' active' : ''}`}
                  onMouseDown={(e) => e.preventDefault()} onClick={() => choose(m.id)}
                  onMouseMove={() => setActive(flat.indexOf(m))}>
                  {m.name}
                  {!m.checked && <span className="major-tag">not yet checked</span>}
                </div>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
