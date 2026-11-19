from django.contrib import admin

from .models import PRAuditLog, PRPostingLog, SupplierChangeLog


@admin.register(PRPostingLog)
class PRPostingLogAdmin(admin.ModelAdmin):
    """Read-only: the PR posting log is append-only, written only by the app."""

    list_display = ('changed_at', 'pr', 'action', 'automatic', 'changed_by_username', 'reason')
    list_filter = ('action', 'automatic')
    search_fields = ('pr__pr_no', 'changed_by_username', 'reason')
    ordering = ('-changed_at', '-id')

    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SupplierChangeLog)
class SupplierChangeLogAdmin(admin.ModelAdmin):
    """Read-only: the supplier change log is append-only, written only by the app."""

    list_display = ('changed_at', 'supplier', 'event_type', 'field_name', 'old_value', 'new_value', 'changed_by_username')
    list_filter = ('event_type', 'changed_by_role')
    search_fields = ('supplier__company_name', 'field_name', 'changed_by_username', 'note')
    ordering = ('-changed_at', '-id')

    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PRAuditLog)
class PRAuditLogAdmin(admin.ModelAdmin):
    """Read-only: the PR edit log is append-only, written only by the app."""

    list_display = ('edited_at', 'pr', 'event_type', 'item_id', 'field_name', 'edited_by_username', 'reason')
    list_filter = ('event_type',)
    search_fields = ('pr__pr_no', 'field_name', 'edited_by_username', 'reason')
    ordering = ('-edited_at', '-id')

    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
