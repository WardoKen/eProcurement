// Labelled KPI tile. `value` of null/undefined renders as 0 with the zero
// hint, so an empty system reads as "nothing yet", not as missing data.
export default function KpiTile({ label, value, unit, hint, zeroHint, icon: Icon, tone }) {
  const numeric = value === null || value === undefined || value === '' ? 0 : value
  const isZero = Number(numeric) === 0
  return (
    <li className={`kpi-tile${tone ? ` tone-${tone}` : ''}`}>
      <p className="kpi-label">
        {Icon && <Icon size={16} aria-hidden="true" />}
        {label}
      </p>
      <p className="kpi-value">
        {numeric}
        {unit && <span className="kpi-unit">{unit}</span>}
      </p>
      {(isZero && zeroHint) ? <p className="kpi-hint">{zeroHint}</p> : hint ? <p className="kpi-hint">{hint}</p> : null}
    </li>
  )
}
