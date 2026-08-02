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
    pr_no = models.CharField(max_length=50, blank=True, null=True)
    responsibility_center_code = models.CharField(max_length=100, blank=True, null=True)
    date = models.DateField(blank=True, null=True)
    purpose = models.TextField(blank=True, null=True)
    requested_by = models.CharField(max_length=255, blank=True, null=True)
    funds_available_by = models.CharField(max_length=255, blank=True, null=True)
    approved_by = models.CharField(max_length=255, blank=True, null=True)
    twg_verified_by = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default=STATUS_UPLOADED)
    grand_total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"PR {self.pr_no or self.id} - {self.entity_name}"


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
        unique_together = ('supplier', 'purchase_request')


class Notification(models.Model):
    TYPE_OPPORTUNITY = 'opportunity'
    TYPE_QUOTATION_SUBMITTED = 'quotation_submitted'
    TYPE_QUOTATION_REVIEW = 'quotation_review'
    TYPE_QUOTATION_AWARDED = 'quotation_awarded'
    TYPE_QUOTATION_REJECTED = 'quotation_rejected'
    TYPE_PROFILE_APPROVED = 'profile_approved'

    TYPE_CHOICES = [
        (TYPE_OPPORTUNITY, 'New Procurement Opportunity'),
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
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.supplier.company_name} - {self.get_notification_type_display()}"

    class Meta:
        ordering = ['-created_at']
