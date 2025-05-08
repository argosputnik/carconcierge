from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.contrib.auth import get_user_model
from django.forms.widgets import HiddenInput, CheckboxSelectMultiple, Select, Textarea
from django.utils.safestring import mark_safe
from django.core.exceptions import ValidationError
from .models import ServiceRequest, Car, JOB_TYPE_CHOICES, Dealer, Inventory, Invoice1, Invoice2
from .validators import validate_license_plate_format
import datetime

User = get_user_model()

# --------------------------
# Bootstrap Mixin
# --------------------------
class BootstrapFormMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if not isinstance(field.widget, (CheckboxSelectMultiple, HiddenInput)):
                attrs = field.widget.attrs
                attrs['class'] = attrs.get('class', '') + ' form-control'


# --------------------------
# Custom Signup Form
# --------------------------
class CustomSignupForm(BootstrapFormMixin, UserCreationForm):
    first_name = forms.CharField(required=True)
    last_name = forms.CharField(required=True)
    email = forms.EmailField(required=True)
    license_plate = forms.CharField(
        max_length=20,
        help_text="Enter your license plate (this will be your username)",
        validators=[validate_license_plate_format],
        required=True
    )

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'license_plate']

    def clean_license_plate(self):
        license_plate = self.cleaned_data.get('license_plate').upper()
        if User.objects.filter(username=license_plate).exists():
            raise forms.ValidationError("That license plate is already registered.")
        return license_plate

    def save(self, commit=True):
        user = super().save(commit=False)
        license_plate = self.cleaned_data['license_plate'].upper()
        user.username = license_plate
        user.role = 'customer'
        if commit:
            user.save()
            Car.objects.create(owner=user, license_plate=license_plate, model='', year=None)
        return user


# --------------------------
# Service Request Form (for customer creation)
# --------------------------
class ServiceRequestForm(BootstrapFormMixin, forms.Form):
    pickup_location = forms.CharField(max_length=255, required=True)
    dropoff_location = forms.CharField(max_length=255, required=True)
    job_type = forms.ChoiceField(choices=JOB_TYPE_CHOICES, required=True)
    description = forms.CharField(
        required=False,
        widget=Textarea(attrs={"rows": 3})
    )

    def __init__(self, *args, **kwargs):
        kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        for field_name in ['pickup_location', 'dropoff_location', 'job_type']:
            if field_name in self.fields:
                attrs = self.fields[field_name].widget.attrs
                attrs['class'] = attrs.get('class', '') + ' form-control'
                if isinstance(self.fields[field_name].widget, Select):
                    attrs['class'] = attrs['class'].replace('form-control', 'form-select')

    def clean_pickup_location(self):
        data = self.cleaned_data['pickup_location']
        cleaned_data = "\n".join([line.strip() for line in data.splitlines() if line.strip()])
        return cleaned_data

    def clean_dropoff_location(self):
        data = self.cleaned_data['dropoff_location']
        cleaned_data = "\n".join([line.strip() for line in data.splitlines() if line.strip()])
        return cleaned_data


# --------------------------
# Edit Request Form
# --------------------------
class EditRequestForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = ServiceRequest
        fields = [
            'pickup_location',
            'dropoff_location',
            'description',
            'status',
            'assigned_to',
            'job_type',
            'concierge_latitude',
            'concierge_longitude',
        ]
        widgets = {
            'description': Textarea(attrs={'rows': 4}),
            'pickup_location': Textarea(attrs={'rows': 3}),
            'dropoff_location': Textarea(attrs={'rows': 3}),
            'job_type': Select(),
            'status': Select(),
            'assigned_to': Select(),
            'concierge_latitude': HiddenInput(),
            'concierge_longitude': HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        instance = kwargs.get('instance')

        for name, field in self.fields.items():
            if isinstance(field.widget, (Select, Textarea)):
                attrs = field.widget.attrs
                attrs['class'] = attrs.get('class', '').replace('form-control', '').strip()
                if isinstance(field.widget, Select):
                    attrs['class'] = attrs.get('class', '') + ' form-select'
                elif isinstance(field.widget, Textarea):
                    attrs['class'] = attrs.get('class', '') + ' form-control'

        # --- Permission-based field disabling and Queryset ---
        if self.user and self.user.role == 'customer':
            for field_name in ['job_type', 'pickup_location', 'dropoff_location', 'assigned_to']:
                if field_name in self.fields:
                    self.fields[field_name].disabled = True

            if 'status' in self.fields and instance:
                current_status_tuple = (instance.status, instance.get_status_display())
                cancel_option_tuple = ('Cancelled', 'Cancelled')
                allowed_choices = [current_status_tuple]
                if current_status_tuple[0] != cancel_option_tuple[0] and cancel_option_tuple[0] in dict(ServiceRequest.STATUS_CHOICES):
                    allowed_choices.append(cancel_option_tuple)
                self.fields['status'].widget.choices = allowed_choices

        elif self.user and self.user.role == 'concierge':
            for field_name in ['job_type', 'pickup_location', 'dropoff_location']:
                if field_name in self.fields:
                    self.fields[field_name].disabled = True

            if 'assigned_to' in self.fields:
                self.fields['assigned_to'].queryset = User.objects.filter(
                    role__in=['dealer', 'concierge']
                ).order_by('first_name', 'last_name')
                self.fields['assigned_to'].required = False

        elif self.user and self.user.role == 'dealer':
            for field_name in ['job_type', 'pickup_location', 'dropoff_location', 'assigned_to']:
                if field_name in self.fields:
                    self.fields[field_name].disabled = True

            if 'status' in self.fields and instance:
                current_status_tuple = (instance.status, instance.get_status_display())
                allowed_choices = [current_status_tuple]
                allowed_transitions = {
                    'Accepted': ['In service'],
                    'In service': ['Delivery'],
                }
                if instance.status in allowed_transitions:
                    for allowed_status in allowed_transitions[instance.status]:
                        if allowed_status != instance.status:
                            if allowed_status in dict(ServiceRequest.STATUS_CHOICES):
                                allowed_choices.append(
                                    (allowed_status, dict(ServiceRequest.STATUS_CHOICES)[allowed_status])
                                )
                self.fields['status'].widget.choices = allowed_choices

        elif self.user and self.user.role == 'owner':
            if 'pickup_location' in self.fields:
                self.fields['pickup_location'].widget.attrs.pop('readonly', None)
                self.fields['pickup_location'].widget.attrs['class'] = (
                    self.fields['pickup_location'].widget.attrs.get('class', '') + ' form-control'
                ).strip()
            if 'dropoff_location' in self.fields:
                self.fields['dropoff_location'].widget.attrs.pop('readonly', None)
                self.fields['dropoff_location'].widget.attrs['class'] = (
                    self.fields['dropoff_location'].widget.attrs.get('class', '') + ' form-control'
                ).strip()
            if 'assigned_to' in self.fields:
                self.fields['assigned_to'].queryset = User.objects.filter(
                    role__in=['concierge', 'dealer']
                ).order_by('first_name', 'last_name')
                self.fields['assigned_to'].required = False

        else:
            for field in self.fields.values():
                field.disabled = True

        if 'assigned_to' in self.fields:
            self.fields['assigned_to'].required = False

    def clean(self):
        cleaned_data = super().clean()
        job_type = cleaned_data.get('job_type')
        description = cleaned_data.get('description')
        status = cleaned_data.get('status')
        assigned_to = cleaned_data.get('assigned_to')
        instance = self.instance

        if job_type == 'Other' and not description and 'description' in self.fields and not self.fields['description'].disabled:
            self.add_error('description', 'Description is required when job type is "Other".')

        if self.user and self.user.role != 'owner' and instance and status != instance.status:
            try:
                original_instance = ServiceRequest.objects.get(pk=instance.pk)
                current_status = original_instance.status
            except ServiceRequest.DoesNotExist:
                current_status = None

            valid_transitions_by_role = {
                'customer': ['Cancelled'],
                'concierge': ['Accepted', 'In service', 'Delivery', 'Complete'],
                'dealer': ['In service', 'Delivery'],
            }

            if self.user.role in valid_transitions_by_role:
                allowed_target_statuses = valid_transitions_by_role[self.user.role]

                if status == 'Delivery' and self.user.role == 'concierge':
                    if assigned_to != self.user or assigned_to is None:
                        self.add_error('status', 'A concierge can only set the status to "Delivery" if assigned to themselves.')
                elif status not in allowed_target_statuses and status != current_status:
                    self.add_error('status', f"Invalid status transition to '{status}' for your role.")

        if assigned_to and assigned_to.role not in ['concierge', 'dealer']:
            self.add_error('assigned_to', 'Service requests can only be assigned to concierges or dealers.')

        return cleaned_data


# --------------------------
# Car Forms
# --------------------------
class CarForm(BootstrapFormMixin, forms.ModelForm):
    year = forms.ChoiceField(
        choices=[(y, y) for y in range(1990, datetime.datetime.now().year + 2)],
        required=True
    )

    class Meta:
        model = Car
        fields = ['model', 'year', 'license_plate']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.license_plate:
            self.initial['license_plate'] = self.instance.license_plate.upper()
        if 'year' in self.fields:
            self.fields['year'].widget.attrs['class'] = (
                self.fields['year'].widget.attrs.get('class', '').replace('form-control', '').strip() + ' form-select'
            )


class AddCarForm(BootstrapFormMixin, forms.ModelForm):
    year = forms.ChoiceField(
        choices=[(y, y) for y in range(1990, datetime.datetime.now().year + 2)],
        required=True
    )

    class Meta:
        model = Car
        fields = ['model', 'year', 'license_plate']

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if 'year' in self.fields:
            self.fields['year'].widget.attrs['class'] = (
                self.fields['year'].widget.attrs.get('class', '').replace('form-control', '').strip() + ' form-select'
            )

    def clean_license_plate(self):
        plate = self.cleaned_data['license_plate'].upper()
        if Car.objects.filter(license_plate__iexact=plate, owner=self.user).exists():
            raise forms.ValidationError("This license plate is already registered to your account.")
        return plate

    def save(self, commit=True):
        car = super().save(commit=False)
        car.owner = self.user
        car.license_plate = car.license_plate.upper()
        if commit:
            car.save()
        return car


# --------------------------
# Account Update Form
# --------------------------
class AccountUpdateForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'address', 'phone']


# --------------------------
# Add Owner Form
# --------------------------
class AddOwnerForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(required=True)
    last_name = forms.CharField(required=True)

    class Meta:
        model = User
        fields = [
            'username',
            'email',
            'first_name',
            'last_name',
        ]

    def __init__(self, *args, **kwargs):
        super(AddOwnerForm, self).__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({
                'class': 'form-control',
                'style': 'max-width: 50%; display: inline-block;',
            })
        self.fields['password2'].widget.attrs.update({
            'class': 'form-control',
            'style': 'max-width: 50%; display: inline-block;',
        })
        self.fields['password1'].widget.attrs.update({
            'class': 'form-control',
            'style': 'max-width: 50%; display: inline-block;',
        })

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = 'owner'
        if commit:
            user.save()
        return user


class AddDealerForm(UserCreationForm):
    job_specialty = forms.MultipleChoiceField(
        choices=JOB_TYPE_CHOICES,
        required=False,
        widget=CheckboxSelectMultiple,
        label="Job Specialty"
    )
    job_specialty_other = forms.CharField(required=False, label="Other Specialty (please specify)")
    email = forms.EmailField(required=True)
    first_name = forms.CharField(required=True)
    last_name = forms.CharField(required=True)
    phone = forms.CharField(required=False)
    address = forms.CharField(required=False)

    class Meta:
        model = User
        fields = [
            'username', 'first_name', 'last_name', 'email', 'phone', 'address',
        ]

    def __init__(self, *args, **kwargs):
        super(AddDealerForm, self).__init__(*args, **kwargs)
        for field in self.fields.values():
            if not isinstance(field.widget, CheckboxSelectMultiple):
                field.widget.attrs.update({
                    'class': 'form-control',
                    'style': 'max-width: 50%; display: inline-block;',
                })
        self.fields['password2'].widget.attrs.update({
            'class': 'form-control',
            'style': 'max-width: 50%; display: inline-block;',
        })
        self.fields['password1'].widget.attrs.update({
            'class': 'form-control',
            'style': 'max-width: 50%; display: inline-block;',
        })

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = 'dealer'
        if commit:
            user.save()
        return user


class EditDealerForm(forms.ModelForm):
    job_specialty_other = forms.CharField(
        required=False,
        label="Other Specialty (please specify)",
        widget=forms.TextInput(attrs={'class': 'form-control', 'style': 'max-width: 50%; display: inline-block;'})
    )
    job_specialty = forms.MultipleChoiceField(
        choices=JOB_TYPE_CHOICES,
        required=False,
        widget=CheckboxSelectMultiple,
        label="Job Specialty"
    )

    class Meta:
        model = Dealer
        fields = ['name', 'phone', 'address', 'job_specialty', 'job_specialty_other']
        widgets = {
            'job_specialty': CheckboxSelectMultiple(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if not isinstance(field.widget, CheckboxSelectMultiple):
                field.widget.attrs.update({
                    'class': 'form-control',
                    'style': 'max-width: 50%; display: inline-block;',
                })

        if self.instance and self.instance.job_specialty:
            specialties = self.instance.job_specialty
            known_specialties = [choice[0] for choice in JOB_TYPE_CHOICES]
            other_specialties_list = [s for s in specialties if s not in dict(JOB_TYPE_CHOICES).keys()]
            self.initial['job_specialty'] = [s for s in specialties if s in dict(JOB_TYPE_CHOICES).keys()]
            if other_specialties_list:
                if 'Other' in dict(JOB_TYPE_CHOICES).keys():
                    self.initial['job_specialty'].append('Other')
                self.initial['job_specialty_other'] = ', '.join(other_specialties_list)

    def clean(self):
        cleaned_data = super().clean()
        job_specialty = cleaned_data.get('job_specialty', [])
        job_specialty_other = cleaned_data.get('job_specialty_other', '').strip()

        if 'Other' in job_specialty and job_specialty_other:
            job_specialty.remove('Other')
            other_specified = [s.strip() for s in job_specialty_other.split(',') if s.strip()]
            cleaned_data['job_specialty'] = job_specialty + other_specified
        elif 'Other' in job_specialty and not job_specialty_other:
            self.add_error('job_specialty_other', 'Please specify the "Other" specialty.')

        return cleaned_data

    def save(self, commit=True):
        dealer = super().save(commit=False)
        if commit:
            dealer.save()
        return dealer


class AddConciergeForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(required=True)
    last_name = forms.CharField(required=True)
    phone = forms.CharField(required=False)
    address = forms.CharField(required=False)

    class Meta:
        model = User
        fields = [
            'username',
            'email',
            'first_name',
            'last_name',
            'phone',
            'address',
        ]

    def __init__(self, *args, **kwargs):
        super(AddConciergeForm, self).__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({
                'class': 'form-control',
                'style': 'max-width: 50%; display: inline-block;',
            })
        self.fields['password2'].widget.attrs.update({
            'class': 'form-control',
            'style': 'max-width: 50%; display: inline-block;',
        })
        self.fields['password1'].widget.attrs.update({
            'class': 'form-control',
            'style': 'max-width: 50%; display: inline-block;',
        })

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = 'concierge'
        if commit:
            user.save()
        return user


class EditConciergeForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone', 'address']

    def __init__(self, *args, **kwargs):
        super(EditConciergeForm, self).__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({
                'class': 'form-control',
                'style': 'max-width: 50%; display: inline-block;',
            })


class AddInventoryForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Inventory
        fields = ['item_number', 'item_name', 'item_quantity', 'item_price']


class EditInventoryForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Inventory
        fields = ['item_number', 'item_name', 'item_quantity', 'item_price']


class Invoice1Form(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Invoice1
        fields = ["price", "currency", "payment_status"]
        widgets = {
            'currency': Select(),
            'payment_status': Select(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in ['currency', 'payment_status']:
            if field_name in self.fields:
                attrs = self.fields[field_name].widget.attrs
                attrs['class'] = attrs.get('class', '').replace('form-control', '').strip() + ' form-select'


class Invoice2Form(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Invoice2
        fields = ["price", "currency", "dealer_name", "payment_status"]
        widgets = {
            'currency': Select(),
            'payment_status': Select(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in ['currency', 'payment_status']:
            if field_name in self.fields:
                attrs = self.fields[field_name].widget.attrs
                attrs['class'] = attrs.get('class', '').replace('form-control', '').strip() + ' form-select'
