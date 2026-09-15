from django.db import models


class Role(models.Model):
    name = models.CharField(max_length=50, unique=True)
    description = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class User(models.Model):
    username = models.CharField(max_length=255, unique=True)
    password_hash = models.CharField(max_length=255)
    full_name = models.CharField(max_length=255, blank=True)
    email = models.EmailField(blank=True)
    unit_office = models.CharField(max_length=255, blank=True)
    role = models.ForeignKey(Role, on_delete=models.PROTECT)
    is_active = models.BooleanField(default=True)
    last_login = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.username


class Category(models.Model):
    name = models.CharField(max_length=255, unique=True)
    description = models.CharField(max_length=500, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Supplier(models.Model):
    company_name = models.CharField(max_length=255)
    business_type = models.CharField(max_length=50, default='Sole Proprietorship')
    business_address = models.TextField(blank=True)
    tin = models.CharField(max_length=100, blank=True)
    contact_person = models.CharField(max_length=255, blank=True)
    contact_phone = models.CharField(max_length=50, blank=True)
    nature_of_business = models.CharField(max_length=255, blank=True)
    goods_services = models.TextField(blank=True)
    products_services = models.TextField(blank=True)
    years_in_business = models.IntegerField(null=True, blank=True)
    email = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=50, default='Pending Review')
    review_remarks = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.company_name


class SupplierCategory(models.Model):
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='supplier_categories')
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='supplier_categories')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('supplier', 'category')

    def __str__(self):
        return f"{self.supplier.company_name} - {self.category.name}"


class SupplierDocument(models.Model):
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='documents')
    doc_type = models.CharField(max_length=100)
    filename = models.CharField(max_length=512)
    original_name = models.CharField(max_length=512, blank=True)
    verification_status = models.CharField(max_length=32, default='Pending')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.supplier.company_name} - {self.doc_type}"


class PurchaseRequest(models.Model):
    STATUS_UPLOADED = 'uploaded'
    STATUS_IN_REVIEW = 'in_review'
    STATUS_MATCHED = 'matched'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'

    STATUS_CHOICES = [
        (STATUS_UPLOADED, 'Uploaded'),
        (STATUS_IN_REVIEW, 'In Review'),
        (STATUS_MATCHED, 'Matched'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_REJECTED, 'Rejected'),
    ]

    entity_name = models.CharField(max_length=255)
    category = models.CharField(max_length=255, blank=True, null=True)
    fund_cluster = models.CharField(max_length=100, blank=True, null=True)
    office_section = models.CharField(max_length=255, blank=True, null=True)
    pr_no = models.CharField(max_length=50, blank=True, null=True, unique=True)
    source_filename = models.CharField(max_length=512, blank=True)
    submitted_by = models.CharField(max_length=255, blank=True)
    responsibility_center_code = models.CharField(max_length=100, blank=True, null=True)
    date = models.DateField(blank=True, null=True)
    purpose = models.TextField(blank=True, null=True)
    requested_by = models.CharField(max_length=255, blank=True, null=True)
    funds_available_by = models.CharField(max_length=255, blank=True, null=True)
    approved_by = models.CharField(max_length=255, blank=True, null=True)
    twg_verified_by = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default=STATUS_UPLOADED)
    grand_total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    # The submitting Buyer's acknowledgement of the Purchase Request Submission
    # Declaration. Recorded for audit; the submitter and time are ``submitted_by``
    # and ``declaration_acknowledged_at`` / ``created_at``.
    declaration_acknowledged = models.BooleanField(default=False)
    declaration_acknowledged_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"PR {self.pr_no or self.id} - {self.entity_name}"


class PRNumberSequence(models.Model):
    key = models.CharField(max_length=20, primary_key=True, default='global')


class PRNumberFormat(models.Model):
    """Admin-configurable PR number format (single-row settings, key='global').

    Numbers are composed as ``[prefix][sep][YYYY][sep][MM][sep]NNN...`` with
    whichever of those segments ``date_granularity`` includes, zero-padded to
    ``sequence_digits``. ``reset_period`` controls when the running sequence
    starts back over at 1 - it is independent of ``date_granularity`` because
    an admin may want the count to reset yearly/monthly even if the printed
    number doesn't itself show a date (see api.views for how that's resolved).
    """

    DATE_GRANULARITY_NONE = 'none'
    DATE_GRANULARITY_YEAR = 'year'
    DATE_GRANULARITY_YEAR_MONTH = 'year_month'
    DATE_GRANULARITY_CHOICES = [
        (DATE_GRANULARITY_NONE, 'No date'),
        (DATE_GRANULARITY_YEAR, 'Year only (YYYY)'),
        (DATE_GRANULARITY_YEAR_MONTH, 'Year and month (YYYY-MM)'),
    ]

    RESET_NEVER = 'never'
    RESET_YEARLY = 'yearly'
    RESET_MONTHLY = 'monthly'
    RESET_PERIOD_CHOICES = [
        (RESET_NEVER, 'Never (accumulate forever)'),
        (RESET_YEARLY, 'Yearly'),
        (RESET_MONTHLY, 'Monthly'),
    ]

    key = models.CharField(max_length=20, primary_key=True, default='global')
    prefix = models.CharField(max_length=20, blank=True, default='')
    date_granularity = models.CharField(
        max_length=12, choices=DATE_GRANULARITY_CHOICES, default=DATE_GRANULARITY_YEAR_MONTH
    )
    separator = models.CharField(max_length=5, default='-')
    sequence_digits = models.PositiveSmallIntegerField(default=3)
    reset_period = models.CharField(max_length=10, choices=RESET_PERIOD_CHOICES, default=RESET_YEARLY)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"PR Number Format ({self.key})"


class PRNotificationSettings(models.Model):
    """Admin-configurable PR status-change email settings (single-row, key='global').

    ``enabled`` is the master switch; each ``notify_*`` flag additionally
    gates whether *reaching that specific status* sends an email at all -
    'uploaded' has no toggle since it's the PR's initial state, never a
    transition. ``mute_automatic_transitions`` only affects the automatic
    matched/in_review flip in ``pr_items_assign_categories`` (which can fire
    repeatedly while an admin is actively re-categorizing items); an explicit
    status change via ``pr_update_status`` always still follows the
    per-status toggles above, regardless of this flag.
    """

    key = models.CharField(max_length=20, primary_key=True, default='global')
    enabled = models.BooleanField(default=True)
    notify_in_review = models.BooleanField(default=True)
    notify_matched = models.BooleanField(default=True)
    notify_approved = models.BooleanField(default=True)
    notify_rejected = models.BooleanField(default=True)
    mute_automatic_transitions = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"PR Notification Settings ({self.key})"


class PurchaseRequestItem(models.Model):
    purchase_request = models.ForeignKey(PurchaseRequest, related_name="line_items", on_delete=models.CASCADE)
    stock_property_no = models.CharField(max_length=100, blank=True, null=True)
    unit = models.CharField(max_length=50, blank=True, null=True)
    item_description = models.TextField(blank=True)
    quantity = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    unit_cost = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_cost = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    category = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return f"{self.purchase_request_id} - {self.item_description[:40]}"


class Quotation(models.Model):
    STATUS_DRAFT = 'draft'
    STATUS_SUBMITTED = 'submitted'
    STATUS_UNDER_REVIEW = 'under_review'
    STATUS_AWARDED = 'awarded'
    STATUS_REJECTED = 'rejected'

    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Draft'),
        (STATUS_SUBMITTED, 'Submitted'),
        (STATUS_UNDER_REVIEW, 'Under Review'),
        (STATUS_AWARDED, 'Awarded'),
        (STATUS_REJECTED, 'Rejected'),
    ]

    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='quotations')
    purchase_request = models.ForeignKey(PurchaseRequest, on_delete=models.CASCADE, related_name='quotations')
    # ``rfq`` may be null for legacy quotations. Included in the uniqueness key so
    # a supplier can quote separately for each category-group RFQ on one PR.
    rfq = models.ForeignKey('RFQ', on_delete=models.SET_NULL, null=True, blank=True, related_name='quotations')
    quoted_amount = models.DecimalField(max_digits=14, decimal_places=2)
    estimated_delivery_days = models.IntegerField(blank=True, null=True)
    warranty_months = models.IntegerField(blank=True, null=True)
    remarks = models.TextField(blank=True)
    attachment_filename = models.CharField(max_length=512, blank=True)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Q-{self.id} ({self.supplier.company_name} / PR {self.purchase_request_id})"

    class Meta:
        unique_together = ('supplier', 'purchase_request', 'rfq')


class Notification(models.Model):
    TYPE_OPPORTUNITY = 'opportunity'
    TYPE_RFQ_RECEIVED = 'rfq_received'
    TYPE_QUOTATION_SUBMITTED = 'quotation_submitted'
    TYPE_QUOTATION_REVIEW = 'quotation_review'
    TYPE_QUOTATION_AWARDED = 'quotation_awarded'
    TYPE_QUOTATION_REJECTED = 'quotation_rejected'
    TYPE_PROFILE_APPROVED = 'profile_approved'

    TYPE_CHOICES = [
        (TYPE_OPPORTUNITY, 'New Procurement Opportunity'),
        (TYPE_RFQ_RECEIVED, 'New Request for Quotation'),
        (TYPE_QUOTATION_SUBMITTED, 'Quotation Submitted'),
        (TYPE_QUOTATION_REVIEW, 'Quotation Under Review'),
        (TYPE_QUOTATION_AWARDED, 'Quotation Awarded'),
        (TYPE_QUOTATION_REJECTED, 'Quotation Rejected'),
        (TYPE_PROFILE_APPROVED, 'Profile Approved'),
    ]

    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=50, choices=TYPE_CHOICES)
    title = models.CharField(max_length=255)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    related_pr_id = models.IntegerField(blank=True, null=True)
    related_quotation_id = models.IntegerField(blank=True, null=True)
    related_rfq_id = models.IntegerField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.supplier.company_name} - {self.get_notification_type_display()}"

    class Meta:
        ordering = ['-created_at']


class RFQ(models.Model):
    STATUS_DRAFT = 'draft'
    STATUS_SENT = 'sent'
    STATUS_QUOTATION_RECEIVED = 'quotation_received'
    STATUS_COMPLETED = 'completed'

    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Draft'),
        (STATUS_SENT, 'Sent'),
        (STATUS_QUOTATION_RECEIVED, 'Quotation Received'),
        (STATUS_COMPLETED, 'Completed'),
    ]

    QUOTATION_BASIS_LOT = 'LOT'
    QUOTATION_BASIS_LINE = 'LINE'
    QUOTATION_BASIS_CHOICES = [
        (QUOTATION_BASIS_LOT, 'By Lot'),
        (QUOTATION_BASIS_LINE, 'By Line'),
    ]

    # How the supplier came to be attached to this RFQ. ``category_match`` is the
    # normal path (supplier registered under the PR procurement category);
    # ``manual_bac`` records a deliberate BAC Secretariat override where the
    # supplier is outside the PR category. This is transaction-specific and never
    # alters the supplier's registered categories.
    SELECTION_CATEGORY_MATCH = 'category_match'
    SELECTION_MANUAL_BAC = 'manual_bac'
    SELECTION_TYPE_CHOICES = [
        (SELECTION_CATEGORY_MATCH, 'Category Match'),
        (SELECTION_MANUAL_BAC, 'Manual BAC Selection'),
    ]

    # How the RFQ reaches the supplier. ``system`` is the normal registered
    # workflow; ``manual`` is a BAC-issued RFQ for an unregistered supplier that
    # the BAC downloads, prints and hands over in person.
    DELIVERY_SYSTEM = 'system'
    DELIVERY_MANUAL = 'manual'
    DELIVERY_METHOD_CHOICES = [
        (DELIVERY_SYSTEM, 'System'),
        (DELIVERY_MANUAL, 'Manual'),
    ]

    # Null while the RFQ is still a draft - the RFQ-YYYY-NNNN number is only
    # assigned when the BAC issues the RFQ, so a preview never consumes a
    # number. Internal RFQ identifier only; the Quotation No. printed on the
    # document is ``quotation_no`` below.
    rfq_no = models.CharField(max_length=50, unique=True, null=True, blank=True)
    purchase_request = models.ForeignKey(PurchaseRequest, on_delete=models.CASCADE, related_name='rfqs')
    # The procurement category group this RFQ serves. A mixed-category PR produces
    # one RFQ per (supplier, category); the RFQ only ever contains that category's
    # items (see ``RFQItem``). Null only for pre-migration RFQs.
    category = models.ForeignKey(
        Category, on_delete=models.PROTECT, null=True, blank=True, related_name='rfqs'
    )
    # Null for a manual / unregistered supplier - that supplier has no eProcure
    # account. Its name lives in ``manual_supplier_name`` as internal metadata
    # only and never appears in the generated RFQ PDF.
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, null=True, blank=True, related_name='rfqs')
    manual_supplier_name = models.CharField(max_length=255, blank=True)
    delivery_method = models.CharField(max_length=20, choices=DELIVERY_METHOD_CHOICES, default=DELIVERY_SYSTEM)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_rfqs')
    subject = models.CharField(max_length=255)
    message = models.TextField()
    mode_of_procurement = models.CharField(max_length=200, blank=True)
    quotation_basis = models.CharField(max_length=10, choices=QUOTATION_BASIS_CHOICES, default=QUOTATION_BASIS_LOT)
    selection_type = models.CharField(
        max_length=32, choices=SELECTION_TYPE_CHOICES, default=SELECTION_CATEGORY_MATCH
    )
    abc = models.CharField(max_length=200, blank=True)
    # "<PR NO>:NN" - the Quotation No. printed on the RFQ, built from the exact
    # PurchaseRequest.pr_no and a 2-digit sequence scoped to that PR alone (see
    # api.views._quotation_number). Blank until the RFQ is issued.
    quotation_no = models.CharField(max_length=100, blank=True)
    additional_notes = models.TextField(blank=True)
    # System-generated RFQ document (BAC → supplier). Never overwritten by a
    # supplier upload.
    pdf_file = models.CharField(max_length=500, blank=True)
    # Completed RFQ document uploaded by the supplier (printed, filled, signed,
    # scanned). Kept separate from ``pdf_file`` for auditability.
    submitted_pdf = models.CharField(max_length=500, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def supplier_display_name(self) -> str:
        if self.supplier_id:
            return self.supplier.company_name
        return self.manual_supplier_name or 'Unregistered supplier'

    @property
    def is_manual(self) -> bool:
        return self.delivery_method == self.DELIVERY_MANUAL or (self.supplier_id is None)

    def __str__(self):
        return f"{self.rfq_no or 'RFQ (draft)'} ({self.supplier_display_name})"


class RFQItem(models.Model):
    """The exact subset of PurchaseRequestItems an RFQ covers.

    Grouping items by category is a transaction concept - the PR items themselves
    are never duplicated. This pure join row makes "which PR items belong to this
    RFQ" deterministic. When an RFQ has no ``rfq_items`` (legacy), consumers fall
    back to every item on the PR.
    """

    rfq = models.ForeignKey(RFQ, on_delete=models.CASCADE, related_name='rfq_items')
    purchase_request_item = models.ForeignKey(
        PurchaseRequestItem, on_delete=models.CASCADE, related_name='rfq_items'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('rfq', 'purchase_request_item')

    def __str__(self):
        return f"{self.rfq_id} - item {self.purchase_request_item_id}"
