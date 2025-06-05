# In your app's urls.py (e.g., main/urls.py)
from django.urls import path
from . import views

urlpatterns = [
    # ... other url patterns ...
    path('service-request/<int:request_id>/location/', views.service_request_location, name='service_request_location'), # <--- CORRECTED PATH
    # ... other url patterns ...
]