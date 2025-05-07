# In your forms.py
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
# Updated mixin to apply form-control to most widgets, but allow overrides
class BootstrapFormMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if not isinstance(field.widget, (CheckboxSelectMultiple, HiddenInput)):
                attrs = field.widget.attrs
                attrs['class'] = attrs.get('class', '') + ' form-control'
                # Optional: Apply a default max-width to text-based inputs if not already set
                # if isinstance(field.widget, (forms.TextInput, Textarea, forms.EmailInput, forms.NumberInput)):
                #     attrs['style'] = attrs.get('style', '') + ' max-width: 50%; display: inline-block;'


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
        fields = ['first_name', 'last_name', 'email', 'license_plate'] # Include username indirectly via license_plate

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
            # Assuming you create the car here on signup
            Car.objects.create(owner=user, license_plate=license_plate, model='', year=None)
        return user


# --------------------------
# Service Request Form (for customer creation)
# --------------------------
class ServiceRequestForm(BootstrapFormMixin, forms.Form):
    # Car fields are handled separately in the view, only need request details here
    # model = forms.CharField(max_length=100, required=True) # Removed - handled by car selection
    # year = forms.ChoiceField( # Removed - handled by car selection
    #     choices=[(y, y) for y in range(1990, datetime.datetime.now().year + 1)],
    #     required=True
    # )
    pickup_location = forms.CharField(max_length=255, required=True)
    dropoff_location = forms.CharField(max_length=255, required=True)
    job_type = forms.ChoiceField(choices=JOB_TYPE_CHOICES, required=True)
    description = forms.CharField(
        required=False,
        widget=Textarea(attrs={"rows": 3}) # Use Textarea widget
    )

    def __init__(self, *args, **kwargs):
        # The user argument is used in the view to filter cars, not needed directly in the form
        kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
         # Apply Bootstrap styling to specific fields
        for field_name in ['pickup_location', 'dropoff_location', 'job_type']:
             if field_name in self.fields:
                 attrs = self.fields[field_name].widget.attrs
                 attrs['class'] = attrs.get('class', '') + ' form-control'
                 if isinstance(self.fields[field_name].widget, Select):
                     attrs['class'] = attrs['class'].replace('form-control', 'form-select')


    def clean_pickup_location(self):
        data = self.cleaned_data['pickup_location']
        # Clean and format location data - example
        cleaned_data = "\n".join([line.strip() for line in data.splitlines() if line.strip()])
        return cleaned_data

    def clean_dropoff_location(self):
         data = self.cleaned_data['dropoff_location']
         # Clean and format location data - example
         cleaned_data = "\n".join([line.strip() for line in data.splitlines() if line.strip()])
         return cleaned_data


# --------------------------
# Edit Request Form
# --------------------------
class EditRequestForm(BootstrapFormMixin, forms.ModelForm):
    # Add hidden fields for location data - now included via Meta fields
    # concierge_latitude = forms.FloatField(widget=HiddenInput(), required=False)
    # concierge_longitude = forms.FloatField(widget=HiddenInput(), required=False)


    class Meta:
        model = ServiceRequest
        # Ensure all fields intended to be on the form are listed
        fields = [
            'pickup_location',
            'dropoff_location',
            'description',
            'status',
            'assigned_to',
            'job_type',
            'concierge_latitude',  # Include hidden fields in Meta
            'concierge_longitude', # Include hidden fields in Meta
        ]
        widgets = {
            'description': Textarea(attrs={'rows': 4}),
            'pickup_location': Textarea(attrs={'rows': 3}), # Use Textarea
            'dropoff_location': Textarea(attrs={'rows': 3}), # Use Textarea
            'job_type': Select(), # Use Select
            'status': Select(),   # Use Select
            'assigned_to': Select(), # Use Select
            'concierge_latitude': HiddenInput(), # Explicitly set widget
            'concierge_longitude': HiddenInput(), # Explicitly set widget
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # Get the current instance if editing
        instance = kwargs.get('instance')

        # Apply Bootstrap styling using the mixin's logic
        # The mixin will add 'form-control' by default, adjust for Select/Textarea
        for name, field in self.fields.items():
             if isinstance(field.widget, (Select, Textarea)):
                 attrs = field.widget.attrs
                 attrs['class'] = attrs.get('class', '').replace('form-control', '').strip() # Remove default form-control
                 if isinstance(field.widget, Select):
                     attrs['class'] = attrs.get('class', '') + ' form-select'
                 elif isinstance(field.widget, Textarea):
                     attrs['class'] = attrs.get('class', '') + ' form-control'


        # --- Permission-based field disabling and Queryset ---
        # Customer can only edit description and status
        if self.user and self.user.role == 'customer':
            for field_name in ['job_type', 'pickup_location', 'dropoff_location', 'assigned_to']:
                if field_name in self.fields: # Check if field exists before disabling
                    self.fields[field_name].disabled = True

            # Limit status choices for customer (usually only Cancelled)
            if 'status' in self.fields and instance: # Ensure instance exists
                 current_status_tuple = (instance.status, instance.get_status_display())
                 cancel_option_tuple = ('Cancelled', 'Cancelled')

                 allowed_choices = [current_status_tuple]
                 if current_status_tuple[0] != cancel_option_tuple[0] and cancel_option_tuple[0] in dict(ServiceRequest.STATUS_CHOICES):
                     allowed_choices.append(cancel_option_tuple)

                 self.fields['status'].widget.choices = allowed_choices


        # Concierge can edit description, status, and assign to dealer/concierge
        elif self.user and self.user.role == 'concierge':
             for field_name in ['job_type', 'pickup_location', 'dropoff_location']:
                if field_name in self.fields:
                    self.fields[field_name].disabled = True

             # Filter assigned_to to only include dealers and concierges, and empty
             if 'assigned_to' in self.fields:
                 self.fields['assigned_to'].queryset = User.objects.filter(role__in=['dealer', 'concierge']).order_by('first_name', 'last_name')
                 self.fields['assigned_to'].required = False # Make assigned_to not required

             # Limit status choices for concierge
             if 'status' in self.fields and instance:
                  current_status_tuple = (instance.status, instance.get_status_display())
                  allowed_choices = [current_status_tuple]
                  # Define allowed transitions for a concierge
                  allowed_transitions = {
                      'Pending': ['Accepted'],
                      'Accepted': ['In service', 'Delivery'], # Concierge can set to In service or Delivery
                      'Delivery': ['Complete'], # Concierge can set to Complete
                  }

                  if instance.status in allowed_transitions:
                      for allowed_status in allowed_transitions[instance.status]:
                          # Add the allowed status option if it's not the current status
                          if allowed_status != instance.status:
                               # Ensure the allowed status is a valid choice
                               if allowed_status in dict(ServiceRequest.STATUS_CHOICES):
                                   allowed_choices.append((allowed_status, dict(ServiceRequest.STATUS_CHOICES)[allowed_status]))

                  self.fields['status'].widget.choices = allowed_choices


        # Dealer can edit description and status (maybe limited status changes)
        elif self.user and self.user.role == 'dealer':
             for field_name in ['job_type', 'pickup_location', 'dropoff_location', 'assigned_to']:
                if field_name in self.fields:
                    self.fields[field_name].disabled = True

             # Limit status options for dealer
             if 'status' in self.fields and instance:
                  current_status_tuple = (instance.status, instance.get_status_display())
                  allowed_choices = [current_status_tuple]
                  # Define the allowed transitions for a dealer
                  allowed_transitions = {
                      'Accepted': ['In service'], # Dealer can take from Accepted
                      'In service': ['Delivery'], # Dealer sets to Delivery when finished
                      # Add other allowed transitions as needed
                  }
                  if instance.status in allowed_transitions:
                      for allowed_status in allowed_transitions[instance.status]:
                          # Add the allowed status option if it's not the current status
                          if allowed_status != instance.status:
                              # Ensure the allowed status is a valid choice
                              if allowed_status in dict(ServiceRequest.STATUS_CHOICES):
                                  allowed_choices.append((allowed_status, dict(ServiceRequest.STATUS_CHOICES)[allowed_status]))

                  self.fields['status'].widget.choices = allowed_choices


        # Owner can edit all fields
        elif self.user and self.user.role == 'owner':
            # Owner can edit locations, so make them editable
            if 'pickup_location' in self.fields:
                self.fields['pickup_location'].widget.attrs.pop('readonly', None)
                self.fields['pickup_location'].widget.attrs['class'] = (self.fields['pickup_location'].widget.attrs.get('class', '') + ' form-control').strip() # Add form-control class
            if 'dropoff_location' in self.fields:
                self.fields['dropoff_location'].widget.attrs.pop('readonly', None)
                self.fields['dropoff_location'].widget.attrs['class'] = (self.fields['dropoff_location'].widget.attrs.get('class', '') + ' form-control').strip() # Add form-control class
            # Owner can assign to any concierge or dealer
            if 'assigned_to' in self.fields:
                self.fields['assigned_to'].queryset = User.objects.filter(role__in=['concierge', 'dealer']).order_by('first_name', 'last_name')
                self.fields['assigned_to'].required = False # Make assigned_to not required
             # Owner can change status to any value - no restriction here

        else:
             # Default for logged-in users with no specific role (shouldn't happen if roles are enforced)
             for field in self.fields.values():
                field.disabled = True


        # Ensure 'assigned_to' is not required if it might be disabled or unassigned
        if 'assigned_to' in self.fields:
             self.fields['assigned_to'].required = False


    def clean(self):
        cleaned_data = super().clean()
        job_type = cleaned_data.get('job_type')
        description = cleaned_data.get('description')
        status = cleaned_data.get('status')
        assigned_to = cleaned_data.get('assigned_to')
        instance = self.instance # Get the current instance

        # If job type is 'Other', description is required
        if job_type == 'Other' and not description and 'description' in self.fields and not self.fields['description'].disabled:
            self.add_error('description', 'Description is required when job type is "Other".')

        # Status transition validation (example: only allow certain status changes)
        if self.user and self.user.role != 'owner' and instance and status != instance.status:
            # Find the original instance from the database to check the real current status
            try:
                original_instance = ServiceRequest.objects.get(pk=instance.pk)
                current_status = original_instance.status
            except ServiceRequest.DoesNotExist:
                 current_status = None # Or handle as appropriate

            # Define valid transitions per role (expanded for clarity)
            valid_transitions_by_role = {
                'customer': ['Cancelled'],
                'concierge': ['Accepted', 'In service', 'Delivery', 'Complete'], # Concierge can move through these
                'dealer': ['In service', 'Delivery'], # Dealer moves from In service to Delivery
                # Owner can transition to anything
            }

            # Check if the attempted transition is valid for the user's role
            if self.user.role in valid_transitions_by_role:
                 allowed_target_statuses = valid_transitions_by_role[self.user.role]

                 # Special handling for 'Delivery' status for concierge - requires self-assignment
                 if status == 'Delivery' and self.user.role == 'concierge':
                      if assigned_to != self.user or assigned_to is None: # Must be assigned to self or just assigned to self
                           self.add_error('status', 'A concierge can only set the status to "Delivery" if assigned to themselves.')
                      # Also check if the transition from current status to Delivery is logically allowed in your workflow
                      # (e.g., maybe only from 'Accepted' or 'In service')
                      # You might need a more detailed transition matrix here if transitions are complex.

                 # General check for other status transitions within the role's allowed targets
                 # Ensure the target status is in the allowed list for the role AND the specific
                 # transition from the current status is also logical.
                 # A simple check: is the target status in the list allowed for this role?
                 elif status not in allowed_target_statuses and status != current_status:
                      self.add_error('status', f"Invalid status transition to '{status}' for your role.")

        # Assignment validation (example: only assign to valid roles)
        if assigned_to and assigned_to.role not in ['concierge', 'dealer']:
             self.add_error('assigned_to', 'Service requests can only be assigned to concierges or dealers.')

        return cleaned_data

# --------------------------
# Car Forms
# --------------------------
class CarForm(BootstrapFormMixin, forms.ModelForm):
    year = forms.ChoiceField(choices=[(y, y) for y in range(1990, datetime.datetime.now().year + 2)], required=True) # Updated year range

    class Meta:
        model = Car
        fields = ['model', 'year', 'license_plate']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.license_plate:
            self.initial['license_plate'] = self.instance.license_plate.upper()
        # Ensure Bootstrap styling for Select
        if 'year' in self.fields:
            self.fields['year'].widget.attrs['class'] = self.fields['year'].widget.attrs.get('class', '').replace('form-control', '').strip() + ' form-select'


class AddCarForm(BootstrapFormMixin, forms.ModelForm):
    year = forms.ChoiceField(choices=[(y, y) for y in range(1990, datetime.datetime.now().year + 2)], required=True) # Updated year range

    class Meta:
        model = Car
        fields = ['model', 'year', 'license_plate']

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
         # Ensure Bootstrap styling for Select
        if 'year' in self.fields:
            self.fields['year'].widget.attrs['class'] = self.fields['year'].widget.attrs.get('class', '').replace('form-control', '').strip() + ' form-select'


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
        ] # password fields are handled by UserCreationForm

    def __init__(self, *args, **kwargs):
        super(AddOwnerForm, self).__init__(*args, **kwargs)
        # Apply Bootstrap styling
        for field in self.fields.values():
             field.widget.attrs.update({
                 'class': 'form-control',
                 'style': 'max-width: 50%; display: inline-block;',
             })
        # Add Bootstrap styling to password fields from UserCreationForm
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
        widget=CheckboxSelectMultiple, # Use CheckboxSelectMultiple widget
        label="Job Specialty"
    )
    job_specialty_other = forms.CharField(required=False, label="Other Specialty (please specify)")
    email = forms.EmailField(required=True) # Ensure email is required
    first_name = forms.CharField(required=True)
    last_name = forms.CharField(required=True)
    phone = forms.CharField(required=False)
    address = forms.CharField(required=False)

    class Meta:
        model = User
        fields = [
            'username', 'first_name', 'last_name', 'email', 'phone', 'address',
        ] # password fields are handled by UserCreationForm

    def __init__(self, *args, **kwargs):
        super(AddDealerForm, self).__init__(*args, **kwargs)
        for field in self.fields.values():
            if not isinstance(field.widget, CheckboxSelectMultiple):
                field.widget.attrs.update({
                    'class': 'form-control',
                    'style': 'max-width: 50%; display: inline-block;',
                })
        # Add Bootstrap styling to password fields from UserCreationForm
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
            'job_specialty': CheckboxSelectMultiple(), # Ensure the widget is set here
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Apply Bootstrap styling
        for field in self.fields.values():
             if not isinstance(field.widget, CheckboxSelectMultiple):
                 field.widget.attrs.update({
                     'class': 'form-control',
                     'style': 'max-width: 50%; display: inline-block;',
                 })


        # Pre-select "Other" and extract custom text
        if self.instance and self.instance.job_specialty:
            specialties = self.instance.job_specialty
            known_specialties = [choice[0] for choice in JOB_TYPE_CHOICES]
            # Find specialties that are not in the predefined choices
            other_specialties_list = [s for s in specialties if s not in dict(JOB_TYPE_CHOICES).keys()]

            # Initialize job_specialty with known specialties
            self.initial['job_specialty'] = [s for s in specialties if s in dict(JOB_TYPE_CHOICES).keys()]

            # If there are 'Other' specialties, add 'Other' to the initial choices and set the 'other' field
            if other_specialties_list:
                # Make sure 'Other' is a valid choice in your JOB_TYPE_CHOICES
                if 'Other' in dict(JOB_TYPE_CHOICES).keys():
                    self.initial['job_specialty'].append('Other')
                self.initial['job_specialty_other'] = ', '.join(other_specialties_list)

    def clean(self):
         cleaned_data = super().clean()
         job_specialty = cleaned_data.get('job_specialty', [])
         job_specialty_other = cleaned_data.get('job_specialty_other', '').strip()

         # If 'Other' is selected in job_specialty and other specialty text is provided,
         # combine them for saving in the model.
         if 'Other' in job_specialty and job_specialty_other:
              # Remove 'Other' from the list as it's a placeholder
              job_specialty.remove('Other')
              # Add the specified other specialties (split by comma)
              other_specified = [s.strip() for s in job_specialty_other.split(',') if s.strip()]
              cleaned_data['job_specialty'] = job_specialty + other_specified
         elif 'Other' in job_specialty and not job_specialty_other:
              # If 'Other' is selected but no text is provided
              self.add_error('job_specialty_other', 'Please specify the "Other" specialty.')

         # If 'Other' was not selected but text was provided (optional handling)
         # elif 'Other' not in job_specialty and job_specialty_other:
         #     self.add_error('job_specialty', 'Please select "Other" for specified specialties.')


         return cleaned_data

    def save(self, commit=True):
        dealer = super().save(commit=False)
        # The job_specialty is already processed in clean(), so just save
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
        ] # password fields are handled by UserCreationForm

    def __init__(self, *args, **kwargs):
        super(AddConciergeForm, self).__init__(*args, **kwargs)
        # Apply Bootstrap styling
        for field in self.fields.values():
             field.widget.attrs.update({
                 'class': 'form-control',
                 'style': 'max-width: 50%; display: inline-block;',
             })
        # Add Bootstrap styling to password fields from UserCreationForm
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
        user.role = 'concierge' # Set role
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

    def __init__(self, *args, **kwargs):
        super(AddInventoryForm, self).__init__(*args, **kwargs)
        # Apply Bootstrap styling using the mixin
        # for field in self.fields.values():
        #     field.widget.attrs.update({
        #         'class': 'form-control',
        #         'style': 'max-width: 50%; display: inline-block;',
        #     })


class EditInventoryForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Inventory
        fields = ['item_number', 'item_name', 'item_quantity', 'item_price']

    def __init__(self, *args, **kwargs):
        super(EditInventoryForm, self).__init__(*args, **kwargs)
        # Apply Bootstrap styling using the mixin
        # for field in self.fields.values():
        #     field.widget.attrs.update({
        #         'class': 'form-control',
        #         'style': 'max-width: 50%; display: inline-block;',
        #     })

class Invoice1Form(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Invoice1
        fields = ["price", "currency", "payment_status"]  # Added payment_status for editing
        widgets = {
             'currency': Select(),
             'payment_status': Select(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Apply Bootstrap styling to Select widgets
        for field_name in ['currency', 'payment_status']:
             if field_name in self.fields:
                  attrs = self.fields[field_name].widget.attrs
                  attrs['class'] = attrs.get('class', '').replace('form-control', '').strip() + ' form-select'


class Invoice2Form(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Invoice2
        fields = ["price", "currency", "dealer_name", "payment_status"] # Added payment_status
        widgets = {
             'currency': Select(),
             'payment_status': Select(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
         # Apply Bootstrap styling to Select widgets
        for field_name in ['currency', 'payment_status']:
             if field_name in self.fields:
                  attrs = self.fields[field_name].widget.attrs
                  attrs['class'] = attrs.get('class', '').replace('form-control', '').strip() + ' form-select'


