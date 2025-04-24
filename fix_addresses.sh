#!/usr/bin/env bash
cd /opt/cars           # ← where your manage.py lives

# (If you use a virtualenv, activate it here:)
# source venv/bin/activate

# Use python3 instead of python
python3 manage.py shell <<'PYCODE'
from main.models import ServiceRequest

for req in ServiceRequest.objects.all():
    parts = [p.strip() for p in req.pickup_location.split(',') if p.strip()]
    req.pickup_location = "\n".join(parts)
    req.save(update_fields=['pickup_location'])

print("✓ All pickup_location fields normalized.")
PYCODE
