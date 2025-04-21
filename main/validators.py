# main/validators.py
import re
from django.core.exceptions import ValidationError

def validate_license_plate_format(value):
    pattern = r'^[A-Z]{2}-\d{3}-[A-Z]{2}$'
    if not re.match(pattern, value.upper()):
        raise ValidationError('License plate must be in the format AA-123-BB (2 letters-3 numbers-2 letters)')
