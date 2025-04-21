from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django import forms
from .models import User, Car, ServiceRequest, Inventory, Dealer, Invoice1, Invoice2
from main.signals import GROUP_TO_ROLE


# ----------------------------
# Custom Admin Form for User
# ----------------------------
class CustomUserAdminForm(forms.ModelForm):
    class Meta:
        model = User
        fields = '__all__'

    class Media:
        js = ('main/js/auto_role_from_group.js',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['role'].required = False
        self.fields['role'].initial = None  # 👈 This shows "--" instead of "Customer"
        self.fields['email'].required = True
        self.fields['first_name'].required = True
        self.fields['last_name'].required = True
        self.fields['phone'].required = False

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if not email:
            raise forms.ValidationError("Email is required.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        groups = self.cleaned_data.get('groups')
        if groups and groups.exists():
            group_name = groups.first().name.lower()
            role = GROUP_TO_ROLE.get(group_name)
            if role:
                user.role = role
        if commit:
            user.save()
            self.save_m2m()
        return user


# ----------------------------
# Custom User Admin
# ----------------------------
class CustomUserAdmin(UserAdmin):
    form = CustomUserAdminForm

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'username', 'email', 'first_name', 'last_name',
                'password1', 'password2', 'phone', 'role', 'groups'
            ),
        }),
    )

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'email', 'address', 'phone')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
        ('Custom Fields', {'fields': ('role',)}),
    )

    list_display = ('username', 'email', 'first_name', 'last_name', 'phone', 'address', 'role', 'is_staff')

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        groups = obj.groups.all()
        if groups.exists():
            group_name = groups.first().name.lower()
            role = GROUP_TO_ROLE.get(group_name)
            if role and obj.role != role:
                obj.role = role
                obj.save()


admin.site.register(User, CustomUserAdmin)


# ----------------------------
# Car Admin
# ----------------------------
@admin.register(Car)
class CarAdmin(admin.ModelAdmin):
    list_display = ('owner', 'model', 'year', 'license_plate')


# ----------------------------
# Service Request Admin
# ----------------------------
@admin.register(ServiceRequest)
class ServiceRequestAdmin(admin.ModelAdmin):
    list_display = (
        'customer', 'car', 'pickup_location', 'dropoff_location',
        'requested_at', 'last_updated', 'status', 'assigned_dealer'
    )
    list_editable = ('status', 'assigned_dealer')

    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))
        if not request.user.is_superuser and getattr(request.user, 'role', None) != 'owner':
            readonly.append('assigned_dealer')
        return readonly

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'assigned_to':
            kwargs["queryset"] = User.objects.exclude(role='customer')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


# ----------------------------
# Inventory Admin
# ----------------------------
@admin.register(Inventory)
class InventoryAdmin(admin.ModelAdmin):
    list_display = ('item_number', 'item_name', 'item_quantity', 'item_price')


# ----------------------------
# Dealer Admin
# ----------------------------
class DealerAdminForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'job_specialty' in self.fields:
            choices = self.fields['job_specialty'].choices
            self.fields['job_specialty'].choices = [c for c in choices if c[0] != 'Other']

    class Meta:
        model = Dealer
        fields = '__all__'


@admin.register(Dealer)
class DealerAdmin(admin.ModelAdmin):
    form = DealerAdminForm
    list_display = ('name', 'address', 'phone', 'job_specialty_display')
    search_fields = ('name', 'address', 'phone')

    def job_specialty_display(self, obj):
        return ", ".join(obj.job_specialty or [])
    job_specialty_display.short_description = "Job Specialties"


# ----------------------------
# Invoice1 Admin
# ----------------------------
@admin.register(Invoice1)
class Invoice1Admin(admin.ModelAdmin):
    list_display = ('first_name', 'last_name', 'email', 'phone', 'address', 'display_price', 'payment_status')

    readonly_fields = (
        'service_request', 'first_name', 'last_name', 'address', 'email', 'phone',
    )

    fields = (
        'service_request', 'first_name', 'last_name', 'address', 'email', 'phone',
        'invoice_date', 'price', 'currency', 'payment_status',
    )

    def display_price(self, obj):
        return f"{obj.price} {obj.currency}" if obj.price and obj.currency else "-"
    display_price.short_description = "Price"

    def save_model(self, request, obj, form, change):
        if change:
            old_obj = Invoice1.objects.get(pk=obj.pk)
            if old_obj.payment_status != obj.payment_status and obj.payment_status == 'Paid':
                if obj.service_request and obj.service_request.status == 'Waiting for Payment':
                    obj.service_request.status = 'Pending'
                    obj.service_request.save()
        super().save_model(request, obj, form, change)


# ----------------------------
# Invoice2 Admin
# ----------------------------
@admin.register(Invoice2)
class Invoice2Admin(admin.ModelAdmin):
    list_display = ('first_name', 'last_name', 'email', 'phone', 'address', 'display_price', 'dealer_name')

    readonly_fields = (
        'service_request', 'first_name', 'last_name', 'address', 'email', 'phone',
        'invoice_date', 'dealer_phone', 'dealer_address'
    )

    fields = (
        'service_request', 'first_name', 'last_name', 'address', 'email', 'phone',
        'invoice_date', 'price', 'currency', 'payment_status',
        'dealer_name', 'dealer_phone', 'dealer_address'
    )

    def display_price(self, obj):
        return f"{obj.price} {obj.currency}" if obj.price and obj.currency else "-"
    display_price.short_description = "Price"

    def get_readonly_fields(self, request, obj=None):
        readonly = list(self.readonly_fields)
        if not request.user.is_superuser and (not request.user.role or request.user.role != 'owner'):
            readonly.append('payment_status')
        return readonly

    def save_model(self, request, obj, form, change):
        if obj.dealer_name:
            try:
                dealer = Dealer.objects.get(name=obj.dealer_name)
                obj.dealer_phone = dealer.phone or ""
                obj.dealer_address = dealer.address or ""
            except Dealer.DoesNotExist:
                pass
        super().save_model(request, obj, form, change)

