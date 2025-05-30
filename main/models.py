from django.contrib.auth.models import AbstractUser
from django.db import models
from django.conf import settings
from django.core.validators import RegexValidator
from .validators import validate_license_plate_format
from multiselectfield import MultiSelectField
from django.utils import timezone


# --------------------------
# Constants
# --------------------------
JOB_TYPE_CHOICES = [
    ('Car Wash', 'Car Wash'),
    ('Oil Change', 'Oil Change'),
    ('Engine Light', 'Engine Light'),
    ('Brake Pad Replacement', 'Brake Pad Replacement'),
    ('Battery Replacement', 'Battery Replacement'),
    ('Other', 'Other'),
]

CURRENCY_CHOICES = [
    ('USD', 'USD'),
    ('EUR', 'Euro'),
    ('GEL', 'GEL'),
]

ROLE_CHOICES = (
    ('customer', 'Customer'),
    ('concierge', 'Concierge'),
    ('dealer', 'Dealer'),
    ('owner', 'Owner'),
)

# --------------------------
# Dealer model
# --------------------------

class Dealer(models.Model):
    user = models.OneToOneField(
        "main.User",
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=20, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    job_specialty = MultiSelectField(choices=JOB_TYPE_CHOICES, blank=True, null=True)

    def __str__(self):
        return self.name


# --------------------------
# User model
# --------------------------
class User(AbstractUser):
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, blank=True, null=True)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    address = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return self.username

    class Meta:
        swappable = 'AUTH_USER_MODEL'

# --------------------------
# Car model
# --------------------------

class Car(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='cars')
    model = models.CharField(max_length=100)
    year = models.PositiveIntegerField(blank=True, null=True)
    license_plate = models.CharField(
        max_length=20,
        unique=True,
        validators=[validate_license_plate_format]
    )

    def __str__(self):
        return f"{self.year} {self.model} ({self.license_plate})"


# --------------------------
# ServiceRequest model
# --------------------------
class ServiceRequest(models.Model):
    STATUS_CHOICES = [
        ('Waiting for Payment', "Waiting for Payment"),
        ('Pending', 'Pending'),
        ('In service', 'In service'),
        ('Delivery', 'Delivery'),
        ('Complete', 'Complete'),
    ]

    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    car = models.ForeignKey('Car', on_delete=models.CASCADE)
    job_type = models.CharField(max_length=50, choices=JOB_TYPE_CHOICES, default='Other')
    description = models.TextField(blank=True, null=True)
    pickup_location = models.CharField(max_length=255)
    dropoff_location = models.CharField(max_length=255)
    requested_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Waiting for Payment')

    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='assigned_requests'
    )

    assigned_dealer = models.ForeignKey(
        Dealer,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='service_requests'
    )

    # For viewing live location on map
    share_location       = models.BooleanField(default=False)
    concierge_latitude   = models.FloatField(null=True, blank=True)
    concierge_longitude  = models.FloatField(null=True, blank=True)

    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Request for {self.car} by {self.customer.username}"

# --------------------------
# RepairNote model
# --------------------------
class RepairNote(models.Model):
    service_request = models.ForeignKey(ServiceRequest, on_delete=models.CASCADE, related_name='notes')
    mechanic = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, limit_choices_to={'role': 'dealer'})
    note = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

# --------------------------
# NotificationLog model
# --------------------------
class NotificationLog(models.Model):
    recipient = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    channel = models.CharField(max_length=20)
    message = models.TextField()
    sent_at = models.DateTimeField(auto_now_add=True)

# --------------------------
# Inventory model
# --------------------------
class Inventory(models.Model):
    class Meta:
        app_label = 'main'

    item_number = models.CharField(max_length=50, unique=True)
    item_name = models.CharField(max_length=255)
    item_quantity = models.PositiveIntegerField()
    item_price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.item_name} ({self.item_number})"

# --------------------------
# Invoice1 model
# --------------------------

class Invoice1(models.Model):
    service_request = models.ForeignKey('ServiceRequest', on_delete=models.CASCADE, null=True, blank=True)
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    address = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    invoice_date = models.DateTimeField(default=timezone.now)
    price = models.CharField(max_length=255, blank=True)
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='GEL')

    PAYMENT_STATUS_CHOICES = [
        ('Unpaid', 'Unpaid'),
        ('Paid', 'Paid'),
    ]
    payment_status = models.CharField(
        max_length=10,
        choices=PAYMENT_STATUS_CHOICES,
        default='Unpaid'
    )

    updated_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        if self.service_request:
            return f"Invoice for {self.first_name} {self.last_name} – Request #{self.service_request.id}"
        return f"Invoice for {self.first_name} {self.last_name}"

class Invoice2(models.Model):
    service_request = models.ForeignKey('ServiceRequest', on_delete=models.CASCADE, null=True, blank=True)
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    address = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    invoice_date = models.DateTimeField()
    price = models.CharField(max_length=255, blank=True)
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='GEL')
    payment_status = models.CharField(
        max_length=10,
        choices=[
            ('Unpaid', 'Unpaid'),
            ('Paid', 'Paid'),
        ],
        default='Unpaid'
    )
    dealer_name = models.CharField(max_length=255)
    dealer_phone = models.CharField(max_length=20, blank=True)
    dealer_address = models.CharField(max_length=255, blank=True)

    updated_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Invoice2 – {self.first_name} {self.last_name} / {self.dealer_name}"
