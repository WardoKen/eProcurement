// Representative API responses used by the flow tests. Shapes follow
// backend/api/views.py so the UI renders the same branches it does in use.

export const adminUser = { role: 'admin', username: 'bac' }
export const buyerUser = { role: 'buyer', username: 'enduser1', name: 'Ana Cruz', email: 'ana@ctu.edu.ph' }
export const supplierUser = { role: 'supplier', username: 'acme', supplier_id: 7, supplier_status: 'Approved' }

export const unnumberedPr = {
  id: 42,
  pr_no: '',
  entity_name: 'Cebu Technological University',
  office_section: 'ICT Office',
  purpose: 'Laptops for the computer laboratory',
  status: 'uploaded',
  items_count: 1,
  grand_total: '2000.00',
  category: '',
  created_at: '2026-11-01T08:00:00Z',
}

export const numberedPr = {
  ...unnumberedPr,
  id: 43,
  pr_no: '2026-11-001',
  status: 'in_review',
  category: 'IT Equipment',
  has_quotation: false,
}

export const prDetails = {
  pr_no: '',
  entity_name: 'Cebu Technological University',
  category: '',
  fund_cluster: '01',
  office_section: 'ICT Office',
  responsibility_center_code: 'RC-100',
  date: '2026-11-01',
  purpose: 'Laptops for the computer laboratory',
  requested_by: 'Ana Cruz',
  funds_available_by: 'Ben Diaz',
  approved_by: 'Carla Esposo',
  twg_verified_by: '',
  grand_total: 2000,
  items: [
    { id: 100, stock_property_no: 'SP-1', unit: 'pc', item_description: 'Laptop, 16GB RAM', quantity: 2, unit_cost: 1000, total_cost: 2000, category: 'IT Equipment' },
  ],
  source_file_url: '',
  source_filename: '',
}

export const dashboardSummary = {
  total_suppliers: 3,
  total_purchase_requests: 4,
  supplier_status_breakdown: [{ status: 'Approved', count: 2 }, { status: 'Pending Review', count: 1 }],
  document_status_breakdown: [{ status: 'Verified', count: 5 }, { status: 'Pending', count: 2 }],
  pr_status_breakdown: [{ status: 'uploaded', count: 1 }, { status: 'in_review', count: 3 }],
  supplier_category_breakdown: [{ category: 'IT Equipment', count: 2 }, { category: 'Janitorial', count: 0 }],
  pr_monthly_volume: [{ month: '2026-10', count: 1 }, { month: '2026-11', count: 3 }],
  rfq_stats: { total_sent: 5, with_response: 2, avg_quotations_per_rfq: 0.4 },
}

export const supplierRow = {
  id: 7,
  company_name: 'Acme Supplies, Inc.',
  status: 'Pending Review',
  email: 'sales@acme.ph',
  contact_person: 'Jo Reyes',
  business_type: 'Corporation',
  categories: ['IT Equipment'],
}

export const supplierProfile = {
  ...supplierRow,
  business_address: 'Cebu City',
  contact_phone: '09171234567',
  products_services: 'Computers and peripherals',
  review_remarks: '',
  documents: [
    { id: 1, doc_type: 'bir_registration', original_name: 'bir.pdf', filename: 'bir.pdf', verification_status: 'Pending', file_url: '/media/bir.pdf', uploaded_at: '2026-10-20T00:00:00Z' },
    { id: 2, doc_type: 'tax_clearance', original_name: 'tax.pdf', filename: 'tax.pdf', verification_status: 'Pending', file_url: '/media/tax.pdf', uploaded_at: '2026-10-20T00:00:00Z' },
  ],
}

export const supplierMatch = {
  pr: { pr_no: '2026-11-001' },
  item_count: 1,
  category_count: 1,
  groups: [
    {
      category: 'IT Equipment',
      category_id: 3,
      item_count: 1,
      items: [{ id: 100, item_description: 'Laptop, 16GB RAM', quantity: 2, unit: 'pc', category: 'IT Equipment' }],
      suppliers: [{ id: 7, company_name: 'Acme Supplies, Inc.', email: 'sales@acme.ph', contact_person: 'Jo Reyes', status: 'Approved', tin: '123-456-789' }],
    },
  ],
  uncategorized_items: [],
}

export const supplierRfq = {
  id: 9,
  rfq_no: 'RFQ-2026-001',
  status: 'sent',
  message: 'Please quote the items below.',
  generated_pdf_url: '/media/rfq-9.pdf',
  submitted_pdf_url: '',
  purchase_request: {
    id: 43,
    pr_no: '2026-11-001',
    office_section: 'ICT Office',
    entity_name: 'Cebu Technological University',
    category: 'IT Equipment',
    items: [{ id: 100, unit: 'pc', item_description: 'Laptop, 16GB RAM', quantity: 2, category: 'IT Equipment' }],
  },
}
