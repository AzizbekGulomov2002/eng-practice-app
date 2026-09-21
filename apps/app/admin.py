from django.contrib import admin
from django.contrib import messages
from .models import TestMaterial, Test, Users
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from .forms import CustomUserCreationForm, CustomUserChangeForm


@admin.register(Users)
class CustomUserAdmin(UserAdmin):
    form = CustomUserChangeForm
    add_form = CustomUserCreationForm
    list_display = ('id', 'username', 'full_name', 'phone', 'role_badge', 'status_badge')
    list_filter = ('role', 'is_active', 'is_staff', 'date_joined')
    search_fields = ('username', 'first_name', 'last_name', 'phone')
    ordering = ('-date_joined',)
    actions = ['activate_users', 'deactivate_users', 'reset_student_passwords']

    def full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"
    full_name.short_description = "Full Name"

    def role_badge(self, obj):
        if obj.role == 'Teacher':
            return format_html(
                '<span style="background-color: #007bff; color: white; padding: 3px 8px; border-radius: 3px; font-size: 11px;">{}</span>',
                'Teacher'
            )
        return format_html(
            '<span style="background-color: #28a745; color: white; padding: 3px 8px; border-radius: 3px; font-size: 11px;">{}</span>',
            'Student'
        )
    role_badge.short_description = "Role"

    def status_badge(self, obj):
        if obj.is_active:
            return format_html('<span style="color: green; font-weight: bold;">✓ Active</span>')
        return format_html('<span style="color: red; font-weight: bold;">✗ Inactive</span>')
    status_badge.short_description = "Status"

    add_fieldsets = (
        ('Basic Information', {
            'classes': ('wide',),
            'fields': ('first_name', 'last_name', 'phone', 'role'),
            'description': 'Phone is used as the login username. There is no public register page.'
        }),
        ('Login password', {
            'classes': ('wide',),
            'fields': ('password1', 'password2'),
            'description': 'Optional. Username is the phone number. If password is empty, an 8-digit password is generated and shown after save.'
        }),
    )

    fieldsets = (
        ('Login Information', {
            'fields': ('username', 'password')
        }),
        ('Personal Information', {
            'fields': ('first_name', 'last_name', 'phone')
        }),
        ('Role', {
            'fields': ('role',),
        }),
        ('Question Parsing', {
            'fields': ('is_parse',),
            'description': 'If False, questions in reading and listening will be displayed as-is without parsing.'
        }),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser'),
            'classes': ('collapse',)
        }),
        ('Important Dates', {
            'fields': ('last_login', 'date_joined'),
            'classes': ('collapse',)
        }),
    )

    def activate_users(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} user(s) have been activated.', messages.SUCCESS)
    activate_users.short_description = "Activate selected users"

    def deactivate_users(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} user(s) have been deactivated.', messages.WARNING)
    deactivate_users.short_description = "Deactivate selected users"

    def reset_student_passwords(self, request, queryset):
        students = queryset.filter(role='Student')
        reset_info = []
        for student in students:
            new_password = student.generate_password()
            student.set_password(new_password)
            student.save()
            reset_info.append(f"{student.username}: {new_password}")
        if reset_info:
            passwords_text = "<br>".join(reset_info)
            self.message_user(
                request,
                format_html(
                    '{} student(s) had their password reset.<br><pre>{}</pre>',
                    len(reset_info),
                    passwords_text
                ),
                messages.SUCCESS
            )
        else:
            self.message_user(request, 'No students found in the selected users.', messages.WARNING)

    def save_model(self, request, obj, form, change):
        if not change:
            if not obj.username:
                obj.username = ''.join(filter(str.isdigit, obj.phone or ''))
            raw_password = form.cleaned_data.get('password1') if form else None
            if not raw_password:
                raw_password = getattr(obj, '_generated_password', None) or obj.generate_password()
                obj.set_password(raw_password)
            obj._generated_password = raw_password
            super().save_model(request, obj, form, change)
            self.message_user(
                request,
                format_html(
                    'New {} created. Give these credentials to the user — there is no register page.<br>'
                    '<strong>Phone / Username:</strong> {}<br>'
                    '<strong>Password:</strong> <span style="color:blue;">{}</span>',
                    obj.role,
                    obj.username,
                    raw_password
                ),
                messages.SUCCESS
            )
        else:
            super().save_model(request, obj, form, change)

    def get_form(self, request, obj=None, **kwargs):
        if obj is None:
            kwargs['form'] = self.add_form
        else:
            kwargs['form'] = self.form
        return super().get_form(request, obj, **kwargs)


@admin.register(Test)
class TestAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "test_type", "test_number", "date")
    list_filter = ("test_type", "date")
    search_fields = ("test_number",)
    ordering = ("-date",)
    readonly_fields = ("test_number", "date")


@admin.register(TestMaterial)
class TestMaterialAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "get_test_type", "get_test_title")

    def get_test_type(self, obj):
        return obj.test.test_type if obj.test else "-"
    get_test_type.short_description = "Test Type"

    def get_test_title(self, obj):
        return obj.test.title if obj.test else "-"
    get_test_title.short_description = "Test Title"
