import { Check } from 'lucide-react'
import { PIPELINE_STAGES, STAGE_COUNT, pipelineStateFor as stateFor } from '../../lib/pipeline'

// The line: eProcure's procurement stations drawn as a transit line
// (DESIGN.md, "The line"). Display only. It never changes a record.
//
//   variant="overview"  dashboard: every station with a count and a note.
//                       A distribution, not progress: a station is occupied
//                       (count > 0) or empty, and the rail stays neutral.
//   variant="record"    one PR: each station named, its state in words
//   variant="explain"   public pages: the route itself, a note per station
//   <PipelineMini />    one segment per station for a table row
//
// A station is done, now, later or stopped (a rejected PR).

const STATE_WORDS = { done: 'Done', now: 'Current', later: 'Not reached', stopped: 'Stopped' }

export default function PipelineLine({
  variant = 'record',
  current = -1,
  stopped = false,
  states,
  counts,
  notes,
  currentText,
  label = 'Procurement progress',
  animate = false,
  onSelectStage,
}) {
  const className = ['pipeline-line', `is-${variant}`, animate ? 'is-animated' : ''].filter(Boolean).join(' ')
  const explain = variant === 'explain'
  const overview = variant === 'overview'
  return (
    <ol className={className} aria-label={label} style={{ '--stations': STAGE_COUNT }}>
      {PIPELINE_STAGES.map((stage, index) => {
        const state = explain ? 'route'
          : overview ? ((counts?.[index] ?? 0) > 0 ? 'occupied' : 'empty')
          : (states?.[index] || stateFor(index, current, stopped))
        const note = notes?.[index]
        let content
        if (variant === 'overview') {
          content = (
            <>
              <span className="pl-name">{stage.label}</span>
              <span className="pl-count">{counts?.[index] ?? 0}</span>
              {note && <span className="pl-note">{note}</span>}
            </>
          )
        } else if (explain) {
          content = (
            <>
              <span className="pl-name">{stage.label}</span>
              {note && <span className="pl-note">{note}</span>}
            </>
          )
        } else {
          content = (
            <>
              <span className="pl-name">{stage.label}</span>
              <span className="pl-state">{state === 'now' && currentText ? currentText : STATE_WORDS[state]}</span>
            </>
          )
        }
        const spokenState = overview && note ? <span className="sr-only">, {note}</span> : null
        return (
          <li
            key={stage.key}
            className={`pl-station is-${state}`}
            style={{ '--i': index }}
            aria-current={state === 'now' ? 'step' : undefined}
          >
            <span className="pl-dot" aria-hidden="true">
              {state === 'done' && variant === 'record' && <Check size={12} strokeWidth={3} />}
            </span>
            {onSelectStage ? (
              <button type="button" className="pl-count-link" onClick={() => onSelectStage(stage.key)}>
                {content}
                {spokenState}
              </button>
            ) : (
              <>
                {content}
                {spokenState}
              </>
            )}
          </li>
        )
      })}
    </ol>
  )
}

// Six segments for a table row, with the position written out for screen
// readers. The visible stage name sits next to it in the row.
export function PipelineMini({ position }) {
  const { index, stopped, label } = position
  const stage = PIPELINE_STAGES[Math.min(index, STAGE_COUNT - 1)]
  const spoken = index >= STAGE_COUNT
    ? 'All stages complete'
    : `Stage ${index + 1} of ${STAGE_COUNT}, ${stage?.label || ''}${stopped ? ', stopped' : ''}${label ? `: ${label}` : ''}`
  return (
    <span className="pl-mini" role="img" aria-label={spoken}>
      {PIPELINE_STAGES.map((item, i) => (
        <i key={item.key} className={stateFor(i, index, stopped) === 'later' ? '' : `is-${stateFor(i, index, stopped)}`} />
      ))}
    </span>
  )
}
