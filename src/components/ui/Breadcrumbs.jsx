// `items`: [{ label, onClick? }]. The last item is the current page.
export default function Breadcrumbs({ items }) {
  if (!items || items.length < 2) return null
  return (
    <nav className="breadcrumbs" aria-label="Breadcrumb">
      <ol>
        {items.map((item, index) => {
          const isCurrent = index === items.length - 1
          return (
            <li key={`${item.label}-${index}`}>
              {isCurrent || !item.onClick ? (
                <span aria-current={isCurrent ? 'page' : undefined}>{item.label}</span>
              ) : (
                <button type="button" onClick={item.onClick}>{item.label}</button>
              )}
            </li>
          )
        })}
      </ol>
    </nav>
  )
}
