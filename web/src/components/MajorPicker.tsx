import { useId, useMemo, useState } from 'react'
import type { MajorEntry } from '../data/dataset'
import { collegeKey, groupMajors, pickerRows } from '../logic/majorSearch'

type Props = { majors: MajorEntry[]; value: string; onChange: (id: string) => void }

/**
 * A combobox grouped by level, then college. Each college is a row that opens and closes its list of majors
 * (the current major's college starts open); typing searches every major and opens every college with a match.
 * Keys: ↑/↓ move, Enter opens a college or chooses a major, Escape closes.
 */
export function MajorPicker({ majors, value, onChange }: Props) {
  const uid = useId()
  const listId = `${uid}-list`
  const current = majors.find((m) => m.id === value)
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(0)
  const [expanded, setExpanded] = useState<ReadonlySet<string>>(new Set())

  const searching = query.trim() !== ''
  const levels = useMemo(() => pickerRows(groupMajors(majors, query), expanded, searching), [majors, query, expanded, searching])
  const flat = levels.flatMap((l) => l.rows)
  const rowId = (key: string) => `${uid}-row-${key.replace(/[^a-z0-9-]/gi, '_')}`

  const close = () => { setOpen(false); setQuery('') }
  const choose = (id: string) => { close(); if (id !== value) onChange(id) }
  const toggle = (key: string) => setExpanded((s) => {
    const next = new Set(s)
    if (next.has(key)) next.delete(key)
    else next.add(key)
    return next
  })
  const show = () => {
    if (open) return
    setOpen(true)
    // Open the current major's college and put the cursor on the current major.
    const start = current ? new Set([...expanded, collegeKey(current.level, current.college)]) : expanded
    setExpanded(start)
    const rows = pickerRows(groupMajors(majors, ''), start, false).flatMap((l) => l.rows)
    setActive(Math.max(0, rows.findIndex((r) => r.kind === 'major' && r.major.id === value)))
  }
  const move = (delta: number) => {
    show()
    if (flat.length > 0) setActive((i) => (Math.min(i, flat.length - 1) + delta + flat.length) % flat.length)
  }
  const activate = (i: number) => {
    const row = flat[i]
    if (!row) return
    if (row.kind === 'college') { if (!searching) toggle(row.key) }
    else choose(row.major.id)
  }

  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); move(1) }
    else if (e.key === 'ArrowUp') { e.preventDefault(); move(-1) }
    else if (e.key === 'Enter' && open && flat[active]) { e.preventDefault(); activate(active) }
    else if (e.key === 'Escape' && open) { e.preventDefault(); close() }
  }

  return (
    <div className="major-picker">
      <label htmlFor={`${uid}-input`}>Major</label>
      <input id={`${uid}-input`} type="text" role="combobox" autoComplete="off" spellCheck={false}
        aria-expanded={open} aria-controls={open ? listId : undefined} aria-autocomplete="list"
        aria-activedescendant={open && flat[active] ? rowId(flat[active].key) : undefined}
        placeholder="Search majors or colleges"
        value={open ? query : current?.name ?? ''}
        onFocus={(e) => { show(); e.currentTarget.select() }}
        onClick={show}
        onChange={(e) => { setOpen(true); setQuery(e.target.value); setActive(0) }}
        onBlur={close} onKeyDown={onKeyDown} />
      {open && (
        <div id={listId} role="listbox" aria-label="Majors" className="major-list">
          {levels.length === 0 && <div className="major-empty">No majors match.</div>}
          {levels.map((l) => (
            <div key={l.label} role="group" aria-labelledby={`${uid}-g-${l.label}`}>
              <div id={`${uid}-g-${l.label}`} className="major-group">{l.label}</div>
              {l.rows.map((r) => {
                const i = flat.indexOf(r)
                const common = {
                  id: rowId(r.key),
                  onMouseDown: (e: React.MouseEvent) => e.preventDefault(),
                  onMouseMove: () => setActive(i),
                  onClick: () => activate(i),
                }
                return r.kind === 'college' ? (
                  <div key={r.key} {...common} role="option" aria-selected={false} aria-expanded={r.open}
                    className={`major-college${i === active ? ' active' : ''}`}>
                    <span className="major-caret" aria-hidden="true">{r.open ? '▾' : '▸'}</span>
                    {r.name}
                    <span className="major-count">{r.count}</span>
                  </div>
                ) : (
                  <div key={r.key} {...common} role="option" aria-selected={r.major.id === value}
                    className={`major-option${i === active ? ' active' : ''}`}>
                    {r.major.name}
                    {!r.major.checked && <span className="major-tag">not yet checked</span>}
                  </div>
                )
              })}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
