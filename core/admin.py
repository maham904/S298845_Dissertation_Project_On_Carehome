from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.core.exceptions import FieldError

from .models import CustomUser, CareHome, ServiceUser, LogEntry, Mapping, IncidentReport, ABCForm, LatestLogEntry


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = (
        'email', 'first_name', 'last_name', 'role', 'carehome', 'is_active', 'is_staff', 'availability_status')
    list_filter = ('role', 'carehome', 'is_active', 'is_staff')
    search_fields = ('email', 'first_name', 'last_name')
    ordering = ('email',)

    # Fields for editing user
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'phone', 'address', 'image', 'additional_info')}),
        ('Role info', {'fields': ('role', 'carehome')}),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        ('Important dates', {'fields': ('last_login', 'date_joined', 'last_active')}),
    )

    # Fields for adding new user
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'first_name', 'last_name', 'password1', 'password2'),
        }),
    )

    # Custom methods
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "carehome":
            if request.user.role == 'manager':
                kwargs["queryset"] = CareHome.objects.all()
            else:
                kwargs["queryset"] = CareHome.objects.none()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def availability_status(self, obj):
        return obj.availability_status

    availability_status.short_description = 'Status'


@admin.register(CareHome)
class CareHomeAdmin(admin.ModelAdmin):
    list_display = ('name', 'postcode')
    search_fields = ('name', 'postcode')


@admin.register(ServiceUser)
class ServiceUserAdmin(admin.ModelAdmin):
    list_display = ('first_name', 'last_name', 'carehome', 'phone')
    list_filter = ('carehome',)
    search_fields = ('first_name', 'last_name', 'phone')


@admin.register(LogEntry)
class LogEntryAdmin(admin.ModelAdmin):
    list_display = ('user', 'carehome', 'service_user', 'shift', 'date', 'time_slot', 'is_locked')
    list_filter = ('carehome', 'shift', 'date', 'is_locked')
    search_fields = ('user__email', 'service_user__first_name', 'service_user__last_name')


@admin.register(Mapping)
class MappingAdmin(admin.ModelAdmin):
    list_display = ['staff', 'created_at']
    filter_horizontal = ['carehomes', 'service_users']


@admin.register(IncidentReport)
class IncidentReportAdmin(admin.ModelAdmin):
    list_display = ('id', 'service_user', 'incident_datetime', 'location', 'staff')
    search_fields = ('service_user__full_name', 'location', 'staff__username')
    list_filter = ('carehome', 'incident_datetime')


@admin.register(ABCForm)
class ABCFormAdmin(admin.ModelAdmin):
    list_display = [
        'service_user',
        'date_of_birth',
        'staff',
        'date_time',
        'created_by',
        'created_at',
        'updated_by_display'  # Custom method instead of direct field
    ]
    list_filter = ['date_time', 'created_by']
    search_fields = ['service_user__first_name', 'service_user__last_name', 'staff']

    def updated_by_display(self, obj):
        """Safe way to display updated_by if the field exists"""
        try:
            return obj.updated_by
        except FieldError:
            return "N/A"

    updated_by_display.short_description = "Last Updated By"

@admin.register(LatestLogEntry)
class LatestLogEntryAdmin(admin.ModelAdmin):
    list_display = ('user', 'carehome', 'service_user', 'shift', 'date', 'status', 'created_at')
    list_filter = ('carehome', 'shift', 'status', 'date')
    search_fields = ('user__email', 'service_user__first_name', 'service_user__last_name')
    ordering = ('-created_at',)

