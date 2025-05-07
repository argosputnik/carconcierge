from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model
#Put user back in .models if it does not work
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
        for _, field in self.fields.items():
            field.widget.attrs.update({
                'class': 'form-control',
                'style': 'max-width: 50%; display: inline-block;',
            })

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
        fields = ['first_name', 'last_name', 'email', 'password1', 'password2', 'license_plate']

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
# Service Request Form
# --------------------------


"""class ServiceRequestForm(BootstrapFormMixin, forms.Form):
    model = forms.CharField(max_length=100, required=True)
    year = forms.ChoiceField(
        choices=[(y, y) for y in range(1990, datetime.datetime.now().year + 1)],
        required=True
    )
    pickup_location = forms.CharField(max_length=255, required=True)
    dropoff_location = forms.CharField(max_length=255, required=True)
    job_type = forms.ChoiceField(choices=JOB_TYPE_CHOICES, required=True)
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3})
    )

    def __init__(self, *args, **kwargs):
        kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

    def clean_pickup_location(self):
        raw = self.cleaned_data['pickup_location']
        # split on commas (or however), then re-join with \n
        parts = [p.strip() for p in raw.split(',') if p.strip()]
        return "\n".join(parts)

"""


class ServiceRequestForm(BootstrapFormMixin, forms.Form):
    pickup_location = forms.CharField(max_length=255, required=True)
    dropoff_location = forms.CharField(max_length=255, required=True)
    job_type = forms.ChoiceField(choices=JOB_TYPE_CHOICES, required=True)
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3})
    )

    def __init__(self, *args, **kwargs):
        kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

    def clean_pickup_location(self):
        data = self.cleaned_data['pickup_location']
        return data.replace('\n', ', ').replace('\r', ', ')


# --------------------------
# Edit Request Form
# --------------------------
class EditRequestForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = ServiceRequest
        # Ensure all fields intended to be on the form are listed
        fields = [
            'pickup_location',
            'dropoff_location',
            'description',
            'status',
            'assigned_to',
            'job_type', # Added job_type if it should be editable/visible
            # Add other relevant fields if necessary
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            # Add widgets for other fields if needed
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

# Determine who can edit sensitive fields
        can_edit_sensitive_fields = user and user.role in ['concierge', 'owner']
        # Determine who can edit location fields (adjust logic as needed)
        can_edit_locations = user and user.role in ['concierge', 'owner', 'customer']

        # --- Disable/Enable Status ---
        if 'status' in self.fields:
            if not can_edit_sensitive_fields:
                self.fields['status'].disabled = True
            else:
                self.fields['status'].disabled = False # Explicitly enable

        # --- Disable/Enable Assigned To & Set Queryset ---
        if 'assigned_to' in self.fields:
            if not can_edit_sensitive_fields:
                self.fields['assigned_to'].disabled = True
                # Optional: Clear queryset when disabled
                self.fields['assigned_to'].queryset = User.objects.none()
            else:
                self.fields['assigned_to'].disabled = False # Explicitly enable
                # Define who can BE assigned (e.g., Concierges and Dealers)
                assignable_roles = ['concierge', 'dealer']
                self.fields['assigned_to'].queryset = User.objects.filter(
                    role__in=assignable_roles
                ).order_by('first_name', 'last_name')
                self.fields['assigned_to'].required = False # Make assignment optional

        # --- Disable/Enable Location Fields ---
        # This makes the template logic for locations simpler if desired
        if 'pickup_location' in self.fields:
            if not can_edit_locations:
                self.fields['pickup_location'].widget.attrs['readonly'] = True
                self.fields['pickup_location'].widget.attrs['class'] += ' form-control-plaintext' # Optional styling
            else:
                 self.fields['pickup_location'].widget.attrs.pop('readonly', None)
                 self.fields['pickup_location'].widget.attrs['class'] = self.fields['pickup_location'].widget.attrs['class'].replace(' form-control-plaintext', '')


        if 'dropoff_location' in self.fields:
            if not can_edit_locations:
                self.fields['dropoff_location'].widget.attrs['readonly'] = True
                self.fields['dropoff_location'].widget.attrs['class'] += ' form-control-plaintext' # Optional styling
            else:
                 self.fields['dropoff_location'].widget.attrs.pop('readonly', None)
                 self.fields['dropoff_location'].widget.attrs['class'] = self.fields['dropoff_location'].widget.attrs['class'].replace(' form-control-plaintext', '')

        # Ensure 'assigned_to' is not required if it might be disabled or unassigned
        if 'assigned_to' in self.fields:
             self.fields['assigned_to'].required = False


# --------------------------
# Car Forms
# --------------------------
class CarForm(forms.ModelForm):
    year = forms.ChoiceField(choices=[(y, y) for y in range(1990, 2026)], required=True)

    class Meta:
        model = Car
        fields = ['model', 'year', 'license_plate']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.license_plate:
            self.initial['license_plate'] = self.instance.license_plate.upper()

class AddCarForm(forms.ModelForm):
    year = forms.ChoiceField(choices=[(y, y) for y in range(1990, 2026)], required=True)

    class Meta:
        model = Car
        fields = ['model', 'year', 'license_plate']

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

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
            'password1',
            'password2',
        ]

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
        widget=forms.CheckboxSelectMultiple,
        label="Job Specialty"
    )
    # Field for "Other" specialty text input
    job_specialty_other = forms.CharField(required=False, label="Other Specialty (please specify)")

    class Meta:
        model = User  # or your custom user/dealer creation mix if applicable
        fields = ['username', 'first_name', 'last_name', 'email', 'phone', 'address', 
                  'job_specialty', 'job_specialty_other', 'password1', 'password2']

    def __init__(self, *args, **kwargs):
        super(AddDealerForm, self).__init__(*args, **kwargs)
        for field in self.fields.values():
            if not isinstance(field.widget, forms.CheckboxSelectMultiple):
                field.widget.attrs.update({
                    'class': 'form-control',
                    'style': 'max-width: 50%; display: inline-block;',
                })

class EditDealerForm(forms.ModelForm):
    job_specialty_other = forms.CharField(
        required=False,
        label="Other Specialty (please specify)"
    )

    class Meta:
        model = Dealer
        fields = ['name', 'phone', 'address', 'job_specialty', 'job_specialty_other']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Initialize form fields
        for field in self.fields.values():
            if not isinstance(field.widget, forms.CheckboxSelectMultiple):
                field.widget.attrs.update({
                    'class': 'form-control',
                    'style': 'max-width: 50%; display: inline-block;',
                })

        # Pre-select "Other" and extract custom text
        if self.instance and self.instance.job_specialty:
            specialties = self.instance.job_specialty  # list
            known_specialties = [choice[0] for choice in JOB_TYPE_CHOICES]
            other_specialties = [s for s in specialties if s not in known_specialties]

            if other_specialties:
                self.initial['job_specialty'].append('Other')
                self.initial['job_specialty_other'] = ', '.join(other_specialties)


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
            'password1',
            'password2'
        ]

    def save(self, commit=True):
        user = super().save(commit=False)
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

class AddInventoryForm(forms.ModelForm):
    class Meta:
        model = Inventory
        fields = ['item_number', 'item_name', 'item_quantity', 'item_price']

    def __init__(self, *args, **kwargs):
        super(AddInventoryForm, self).__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({
                'class': 'form-control',
                'style': 'max-width: 50%; display: inline-block;',
            })


class EditInventoryForm(forms.ModelForm):
    class Meta:
        model = Inventory
        fields = ['item_number', 'item_name', 'item_quantity', 'item_price']

    def __init__(self, *args, **kwargs):
        super(EditInventoryForm, self).__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({
                'class': 'form-control',
                'style': 'max-width: 50%; display: inline-block;',
            })

class Invoice1Form(forms.ModelForm):
    class Meta:
        model = Invoice1
        fields = ["price", "currency"]  # plus any other editable fields

class Invoice2Form(forms.ModelForm):
    class Meta:
        model = Invoice2
        fields = ["price", "currency", "dealer_name"]
