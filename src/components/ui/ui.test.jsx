import { describe, expect, it, vi } from 'vitest'
import { useState } from 'react'
import { render, renderHook, act, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import Modal from './Modal'
import ConfirmDialog from './ConfirmDialog'
import useConfirm from './useConfirm'
import useTableControls from './useTableControls'
import ProcurementStepper from './ProcurementStepper'
import KpiTile from './KpiTile'
import Breadcrumbs from './Breadcrumbs'
import ErrorBoundary from './ErrorBoundary'

function ModalHarness() {
  const [open, setOpen] = useState(false)
  return (
    <>
      <button type="button" onClick={() => setOpen(true)}>Open</button>
      {open && (
        <Modal labelledBy="t" onClose={() => setOpen(false)}>
          <h2 id="t">Edit record</h2>
          <button type="button">First</button>
          <button type="button">Last</button>
        </Modal>
      )}
    </>
  )
}

describe('Modal', () => {
  it('moves focus in, traps Tab, closes on Escape and restores focus', async () => {
    const user = userEvent.setup()
    render(<ModalHarness />)
    const opener = screen.getByRole('button', { name: 'Open' })
    await user.click(opener)

    const dialog = screen.getByRole('dialog', { name: 'Edit record' })
    expect(dialog).toHaveFocus()
    await user.tab()
    expect(screen.getByRole('button', { name: 'First' })).toHaveFocus()
    await user.tab()
    expect(screen.getByRole('button', { name: 'Last' })).toHaveFocus()
    await user.tab()
    expect(screen.getByRole('button', { name: 'First' })).toHaveFocus()
    await user.tab({ shift: true })
    expect(screen.getByRole('button', { name: 'Last' })).toHaveFocus()

    await user.keyboard('{Escape}')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(opener).toHaveFocus()
  })

  it('does not close on Escape while not dismissible', async () => {
    const user = userEvent.setup()
    const onClose = vi.fn()
    render(<Modal labelledBy="t" onClose={onClose} dismissible={false}><h2 id="t">Busy</h2></Modal>)
    await user.keyboard('{Escape}')
    expect(onClose).not.toHaveBeenCalled()
  })
})

describe('ConfirmDialog', () => {
  it('is an alertdialog that states the consequence and focuses Cancel', () => {
    render(
      <ConfirmDialog title="Send RFQ?" consequence="It can no longer be edited." confirmLabel="Send RFQ" onConfirm={() => {}} onCancel={() => {}}>
        <p>Send to sales@acme.ph</p>
      </ConfirmDialog>,
    )
    const dialog = screen.getByRole('alertdialog', { name: 'Send RFQ?' })
    expect(dialog).toHaveAccessibleDescription(/no longer be edited/)
    expect(within(dialog).getByRole('button', { name: 'Cancel' })).toHaveFocus()
  })

  it('useConfirm resolves true on confirm and false on cancel', async () => {
    const user = userEvent.setup()
    const results = []
    function Harness() {
      const [dialog, confirm] = useConfirm()
      return (
        <>
          <button type="button" onClick={async () => results.push(await confirm({ title: 'Proceed?', confirmLabel: 'Proceed' }))}>Ask</button>
          {dialog}
        </>
      )
    }
    render(<Harness />)
    await user.click(screen.getByRole('button', { name: 'Ask' }))
    await user.click(screen.getByRole('button', { name: 'Proceed' }))
    await user.click(screen.getByRole('button', { name: 'Ask' }))
    await user.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(results).toEqual([true, false])
  })
})

describe('useTableControls', () => {
  const rows = Array.from({ length: 23 }, (_, index) => ({ id: index + 1, name: `Item ${index + 1}`, total: (index * 7) % 10 }))

  it('paginates, searches and sorts without mutating the input', () => {
    const original = rows.map((row) => row.id)
    const { result } = renderHook(() => useTableControls(rows, {
      search: (row) => [row.name],
      sorters: { total: (row) => row.total, name: (row) => row.name },
      pageSize: 10,
    }))
    expect(result.current.rows).toHaveLength(10)
    expect(result.current.pageCount).toBe(3)

    act(() => result.current.setPage(3))
    expect(result.current.rows.map((row) => row.id)).toEqual([21, 22, 23])

    act(() => result.current.setQuery('item 2'))
    expect(result.current.page).toBe(1)
    expect(result.current.total).toBe(5) // Item 2, 20, 21, 22, 23

    act(() => result.current.setQuery(''))
    act(() => result.current.toggleSort('name'))
    expect(result.current.ariaSort('name')).toBe('ascending')
    expect(result.current.rows[0].name).toBe('Item 1')
    expect(result.current.rows[1].name).toBe('Item 2') // numeric-aware
    act(() => result.current.toggleSort('name'))
    expect(result.current.rows[0].name).toBe('Item 23')
    expect(rows.map((row) => row.id)).toEqual(original)
  })
})

describe('ProcurementStepper', () => {
  it.each([
    ['draft', 'RFQ Prepared'],
    ['sent', 'Quotation Received'],
  ])('marks the current step for %s', (status, currentLabel) => {
    render(<ProcurementStepper status={status} />)
    const current = screen.getByRole('listitem', { current: 'step' })
    expect(current).toHaveTextContent(currentLabel)
  })

  it('shows only the steps eProcure handles, all done once a quotation is in', () => {
    render(<ProcurementStepper status="quotation_received" />)
    const steps = screen.getAllByRole('listitem')
    expect(steps.map((step) => step.querySelector('.procurement-step-label').textContent))
      .toEqual(['RFQ Prepared', 'RFQ Sent', 'Quotation Received'])
    steps.forEach((step) => expect(step).toHaveTextContent('Completed'))
    expect(screen.queryByText(/evaluation|po issuance/i)).not.toBeInTheDocument()
  })

  it('tells a supplier their quotation was submitted once it is uploaded', () => {
    render(<ProcurementStepper status="quotation_received" audience="supplier" />)
    const steps = screen.getAllByRole('listitem')
    expect(screen.queryByRole('listitem', { current: 'step' })).not.toBeInTheDocument()
    expect(steps[2]).toHaveTextContent(/upload quotation.*submitted to the bac/i)
  })
})

describe('display components', () => {
  it('KpiTile shows zero with its zero hint', () => {
    render(<ul><KpiTile label="RFQs sent" value={undefined} unit="RFQs" zeroHint="No RFQs issued yet." /></ul>)
    expect(screen.getByText('0')).toBeInTheDocument()
    expect(screen.getByText('No RFQs issued yet.')).toBeInTheDocument()
  })

  it('Breadcrumbs marks the last item as the current page', () => {
    render(<Breadcrumbs items={[{ label: 'Admin', onClick: () => {} }, { label: 'Supplier Matching' }]} />)
    expect(screen.getByRole('navigation', { name: 'Breadcrumb' })).toBeInTheDocument()
    expect(screen.getByText('Supplier Matching')).toHaveAttribute('aria-current', 'page')
  })

  it('ErrorBoundary shows recovery actions and retries', async () => {
    const user = userEvent.setup()
    vi.spyOn(console, 'error').mockImplementation(() => {})
    let shouldThrow = true
    function Flaky() {
      if (shouldThrow) throw new Error('boom')
      return <p>Recovered</p>
    }
    render(<ErrorBoundary><Flaky /></ErrorBoundary>)
    expect(screen.getByRole('alert')).toHaveTextContent(/could not be displayed/i)
    shouldThrow = false
    await user.click(screen.getByRole('button', { name: /try again/i }))
    expect(screen.getByText('Recovered')).toBeInTheDocument()
  })
})
