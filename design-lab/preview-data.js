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

const rfq = (id, prNo, supplierName, fields = {}) => ({
  id,
  rfq_no: `RFQ-${prNo}:${String(id % 7 + 1).padStart(2, '0')}`,
  status: 'sent',
  has_response: false,
  supplier: { id: 300 + id, company_name: supplierName },
  sent_at: iso(6),
  submitted_at: null,
  generated_pdf_url: '/media/rfq.pdf',
  submitted_pdf_url: '',
  ...fields,
})

export const rfqGroups = {
  purchase_requests: [
    {
      purchase_request: { id: 11, pr_no: '2026-10-004', category: 'Information Technology Parts & Peripheral' },
      rfq_summary: { status: 'responses_in_progress', sent: 3, responses_received: 1, awaiting_response: 2, category_count: 1 },
      categories: [{
        category: 'Information Technology Parts & Peripheral', item_count: 7, rfq_count: 3, response_count: 1,
        rfqs: [
          rfq(41, '2026-10-004', 'Mactan Tech Parts Corp.', { status: 'quotation_received', has_response: true, submitted_at: iso(2), submitted_pdf_url: '/media/q.pdf' }),
          rfq(42, '2026-10-004', 'Cebu Computer Depot'),
          rfq(43, '2026-10-004', 'Visayan Systems Trading'),
        ],
      }],
      rfqs: [],
    },
    {
      purchase_request: { id: 10, pr_no: '2026-09-003', category: 'Janitorial Supplies' },
      rfq_summary: { status: 'responses_in_progress', sent: 2, responses_received: 1, awaiting_response: 1, category_count: 1 },
      categories: [{ category: 'Janitorial Supplies', item_count: 4, rfq_count: 2, response_count: 1, rfqs: [
        rfq(44, '2026-09-003', 'Cebu Clean Solutions', { status: 'quotation_received', has_response: true, submitted_at: iso(5), submitted_pdf_url: '/media/q.pdf' }),
        rfq(45, '2026-09-003', 'Tuburan Office Mart'),
      ] }],
      rfqs: [],
    },
    {
      purchase_request: { id: 9, pr_no: '2026-09-002', category: 'Janitorial Supplies' },
      rfq_summary: { status: 'all_responses_received', sent: 3, responses_received: 3, awaiting_response: 0, category_count: 1 },
      categories: [{ category: 'Janitorial Supplies', item_count: 5, rfq_count: 3, response_count: 3, rfqs: [
        rfq(46, '2026-09-002', 'Cebu Clean Solutions', { status: 'quotation_received', has_response: true, submitted_at: iso(9), submitted_pdf_url: '/media/q.pdf' }),
        rfq(47, '2026-09-002', 'Tuburan Office Mart', { status: 'quotation_received', has_response: true, submitted_at: iso(8), submitted_pdf_url: '/media/q.pdf' }),
        rfq(48, '2026-09-002', 'Danao Hardware Supply', { status: 'quotation_received', has_response: true, submitted_at: iso(7), submitted_pdf_url: '/media/q.pdf' }),
      ] }],
      rfqs: [],
    },
  ],
}

export const supplierMatch = {
  pr: { pr_no: '2026-11-013' },
  item_count: 4,
  category_count: 1,
  groups: [{
    category: 'Advertising Agency Services',
    category_id: 3,
    item_count: 4,
    items: prDetails(18).items,
    suppliers: [
      { id: 327, company_name: 'Island Signage Co.', email: 'quotes@islandsignage.ph', contact_person: 'Ramil Ouano', status: 'Approved', compliance_status: 'Eligible', compliance_percentage: 100 },
      { id: 331, company_name: 'Visayas Print Hub, Inc.', email: 'sales@visayasprint.ph', contact_person: 'Joy Lim', status: 'Approved', compliance_status: 'Eligible', compliance_percentage: 100 },
      { id: 340, company_name: 'Cebu Large Format Prints', email: 'bids@cebulfp.ph', contact_person: 'Arnel Tan', status: 'Approved', compliance_status: 'Eligible', compliance_percentage: 100 },
    ],
  }],
  uncategorized_items: [],
}

export const manualRfqs = {
  rfqs: [
    { id: 61, manual_supplier_name: 'Bantayan Printing Press', status_label: 'Awaiting completed RFQ', has_response: false, purchase_request: { id: 18, pr_no: '2026-11-013' }, quotation_no: 'Q-2026-11-013-M1', rfq_no: 'RFQ-2026-11-013:04', created_by: 'admintest', sent_at: iso(1), created_at: iso(1) },
  ],
}
