// Sample API responses for the design preview (design-lab/preview.html).
// Shapes follow backend/api/views.py, like src/test/fixtures.js. The
// records mirror the local data (CTU Tuburan PRs, approved suppliers) plus
// a few PRs at other stages, so every station on the line has something.

const iso = (daysAgo, hour = 9) => {
  const d = new Date(Date.UTC(2026, 10, 19, hour))
  d.setUTCDate(d.getUTCDate() - daysAgo)
  return d.toISOString()
}

const pr = (id, fields) => ({
  id,
  pr_no: '',
  entity_name: 'CTU-Tuburan Campus',
  office_section: 'MIS',
  purpose: 'Procurement of advertising materials, including tarpaulin banners and standees',
  status: 'matched',
  items_count: 4,
  grand_total: '14050.00',
  category: 'Advertising Agency Services',
  created_at: iso(id),
  is_posted: false,
  posted_at: null,
  posted_by: '',
  rfq_sent_count: 0,
  rfq_response_count: 0,
  submitted_by: 'enduser1',
  source_file_url: '',
  stage_timestamps: { submitted: iso(id), supplier_matching: null, rfq_sent: null, supplier_response: null },
  ...fields,
})

export const prList = [
  pr(21, { pr_no: '', status: 'uploaded', office_section: 'Registrar', purpose: 'Printer toner and continuous forms for enrolment', grand_total: '18640.00', items_count: 6, category: '' }),
  pr(20, { pr_no: '', status: 'uploaded', entity_name: 'CTU-Balamban Campus', office_section: 'Library', purpose: 'Reference books for the engineering collection', grand_total: '52300.00', items_count: 12, category: '' }),
  pr(19, { pr_no: '2026-11-014', status: 'in_review', office_section: 'Supply Office', purpose: 'Janitorial supplies for the second semester', grand_total: '23415.50', items_count: 9, category: 'Janitorial Supplies' }),
  pr(18, { pr_no: '2026-11-013', purpose: 'Procurement of advertising materials, including tarpaulin banners and standees' }),
  pr(17, { pr_no: '2026-11-012', entity_name: 'CTU-Balamban Campus', office_section: 'SAO' }),
  pr(16, { pr_no: '2026-11-011' }),
  pr(15, { pr_no: '2026-11-010' }),
  pr(14, { pr_no: '2026-11-009' }),
  pr(13, { pr_no: '2026-11-008', is_posted: true, posted_at: iso(2), posted_by: 'admintest' }),
  pr(12, { pr_no: '2026-11-007', is_posted: true, posted_at: iso(3), posted_by: 'admintest' }),
  pr(11, { pr_no: '2026-10-004', office_section: 'ICT Office', purpose: 'IT parts and peripherals for the computer laboratory', category: 'Information Technology Parts & Peripheral', grand_total: '48320.00', items_count: 7, is_posted: true, posted_at: iso(9), posted_by: 'admintest', rfq_sent_count: 3, rfq_response_count: 1 }),
  pr(10, { pr_no: '2026-09-003', office_section: 'Registrar', purpose: 'Printer toner and cleaning supplies', category: 'Janitorial Supplies', grand_total: '22780.00', is_posted: true, posted_at: iso(14), posted_by: 'admintest', rfq_sent_count: 2, rfq_response_count: 1 }),
  pr(9, { pr_no: '2026-09-002', office_section: 'Engineering', purpose: 'Laboratory consumables for the materials testing course', category: 'Janitorial Supplies', grand_total: '31950.00', is_posted: true, posted_at: iso(20), posted_by: 'admintest', rfq_sent_count: 3, rfq_response_count: 3 }),
  pr(8, { pr_no: '2026-09-001', status: 'approved', office_section: 'Accounting', purpose: 'Office supplies for the accounting section', category: 'Janitorial Supplies', grand_total: '9875.00', is_posted: true, posted_at: iso(30), posted_by: 'admintest', rfq_sent_count: 2, rfq_response_count: 2 }),
  pr(7, { pr_no: '2026-08-006', status: 'rejected', office_section: 'Guidance', purpose: 'Furniture for the counselling room', grand_total: '64000.00', category: '' }),
]

const supplier = (id, company_name, status, email, categories) => ({
  id, company_name, status, email, categories,
  contact_person: 'Sales desk', business_type: 'Corporation', created_at: iso(id % 20),
})

export const suppliers = [
  supplier(331, 'Visayas Print Hub, Inc.', 'Pending Review', 'sales@visayasprint.ph', ['Advertising Agency Services']),
  supplier(330, 'Cebu Clean Solutions', 'For Compliance', 'orders@cebuclean.ph', ['Janitorial Supplies']),
  supplier(329, 'Tuburan Office Mart', 'Approved', 'hello@tuburanmart.ph', ['Janitorial Supplies', 'Office Supplies']),
  supplier(328, 'Mactan Tech Parts Corp.', 'Approved', 'bids@mactantech.ph', ['Information Technology Parts & Peripheral']),
  supplier(327, 'Island Signage Co.', 'Approved', 'quotes@islandsignage.ph', ['Advertising Agency Services']),
  supplier(326, 'Danao Hardware Supply', 'Rejected', 'danao.hw@example.ph', ['Construction Materials']),
]

export const dashboardSummary = {
  total_suppliers: 331,
  total_purchase_requests: prList.length,
  supplier_status_breakdown: [
    { status: 'Approved', count: 327 }, { status: 'Pending Review', count: 1 }, { status: 'For Compliance', count: 1 }, { status: 'Rejected', count: 2 },
  ],
  document_status_breakdown: [{ status: 'Verified', count: 1308 }, { status: 'Pending', count: 6 }, { status: 'Rejected', count: 2 }],
  pr_status_breakdown: [
    { status: 'uploaded', count: 2 }, { status: 'in_review', count: 1 }, { status: 'matched', count: 10 }, { status: 'approved', count: 1 }, { status: 'rejected', count: 1 },
  ],
  supplier_category_breakdown: [
    { category: 'Advertising Agency Services', count: 24 }, { category: 'Information Technology Parts & Peripheral', count: 19 },
    { category: 'Janitorial Supplies', count: 14 }, { category: 'Office Supplies', count: 11 }, { category: 'Construction Materials', count: 0 },
  ],
  pr_monthly_volume: [
    { month: '2026-06', count: 2 }, { month: '2026-07', count: 1 }, { month: '2026-08', count: 3 },
    { month: '2026-09', count: 4 }, { month: '2026-10', count: 2 }, { month: '2026-11', count: 9 },
  ],
  rfq_stats: { total_sent: 10, with_response: 7, avg_quotations_per_rfq: 0.7 },
}

export const prDetails = (id) => {
  const record = prList.find((row) => row.id === Number(id)) || prList[3]
  return {
    ...record,
    fund_cluster: '01',
    responsibility_center_code: 'RC-2026-114',
    date: '2026-11-04',
    requested_by: 'Maria Lourdes Abellana',
    funds_available_by: 'Ramon Villaflor',
    approved_by: 'Dr. Edgardo Cabahug',
    twg_verified_by: '',
    items: [
      { id: id * 10 + 1, stock_property_no: '', unit: 'pc', item_description: 'Tarpaulin banner, 3 x 6 ft, full colour', quantity: 10, unit_cost: 650, total_cost: 6500, category: record.category },
      { id: id * 10 + 2, stock_property_no: '', unit: 'pc', item_description: 'Roll-up standee, 2 x 5 ft, with carry bag', quantity: 3, unit_cost: 1450, total_cost: 4350, category: record.category },
      { id: id * 10 + 3, stock_property_no: '', unit: 'set', item_description: 'Acrylic sign holder, A4', quantity: 8, unit_cost: 250, total_cost: 2000, category: record.category },
      { id: id * 10 + 4, stock_property_no: '', unit: 'roll', item_description: 'Double-sided mounting tape', quantity: 12, unit_cost: 100, total_cost: 1200, category: record.category },
    ],
    source_filename: '',
  }
}
