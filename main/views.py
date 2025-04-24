from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib import messages
from django import forms
from django.db import connection
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_POST
from django.http import HttpResponseForbidden, HttpResponse
from django.contrib.auth import get_user_model

from .forms import CustomSignupForm, ServiceRequestForm, EditRequestForm
from .models import ServiceRequest, Car

User = get_user_model()

# --------------------------
# Role Checks
# --------------------------
def is_concierge(user):
    return user.is_authenticated and user.role == 'concierge'

def is_dealer(user):
    return user.is_authenticated and user.role == 'dealer'

# --------------------------
# Homepage
# --------------------------
def home(request):
    return render(request, 'main/home.html')

# --------------------------
# Signup
# --------------------------
def signup_view(request):
    if request.method == 'POST':
        form = CustomSignupForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.role = 'customer'
            user.save()
            login(request, user)
            return redirect('home')
    else:
        form = CustomSignupForm()
    return render(request, 'main/signup.html', {'form': form})

# --------------------------
# Dashboards
# --------------------------
@login_required
def customer_dashboard(request):
    status_filter = request.GET.get('status', 'all')
    service_requests = ServiceRequest.objects.filter(customer=request.user)

    if status_filter != 'all':
        service_requests = service_requests.filter(status=status_filter)

    return render(request, 'main/customer_dashboard.html', {
        'open_requests': service_requests,
        'open_request_count': service_requests.count(),
        'status_filter': status_filter
    })

@login_required
@user_passes_test(is_concierge)
def concierge_dashboard(request):
    status_filter = request.GET.get('status', 'all')
    open_requests = ServiceRequest.objects.all().order_by('-requested_at')
    if status_filter != 'all':
        open_requests = open_requests.filter(status=status_filter)

    return render(request, 'main/concierge_dashboard.html', {
        'open_requests': open_requests,
        'open_request_count': open_requests.count(),
        'status_filter': status_filter
    })

@login_required
@user_passes_test(is_dealer)
def dealer_dashboard(request):
    status_filter = request.GET.get('status', 'all')
    open_requests = ServiceRequest.objects.all().order_by('-requested_at')
    if status_filter != 'all':
        open_requests = open_requests.filter(status=status_filter)

    return render(request, 'main/dealer_dashboard.html', {
        'open_requests': open_requests,
        'open_request_count': open_requests.count(),
        'status_filter': status_filter
    })

@login_required
def owner_dashboard(request):
    return render(request, 'main/owner_dashboard.html')

# --------------------------
# Service Request Views
# --------------------------
@login_required
def create_service_request(request):
    if request.method == 'POST':
        form = ServiceRequestForm(request.POST)
        if form.is_valid():
            car = Car.objects.create(
                owner=request.user,
                model=form.cleaned_data['model'],
                year=form.cleaned_data['year'],
                license_plate=form.cleaned_data['license_plate']
            )
            ServiceRequest.objects.create(
                customer=request.user,
                car=car,
                description=form.cleaned_data['description'],
                pickup_location=form.cleaned_data['pickup_location'],
                dropoff_location=form.cleaned_data['dropoff_location'],
            )
            return redirect('customer_dashboard')
    else:
        form = ServiceRequestForm()
    return render(request, 'main/service_request_form.html', {'form': form})

@login_required
def view_service_request(request, request_id):
    sr = get_object_or_404(ServiceRequest, id=request_id)
    if request.user != sr.customer and request.user.role not in ['concierge', 'dealer']:
        return HttpResponseForbidden()
    return render(request, 'main/view_service_request.html', {'service_request': sr})

@login_required
def edit_service_request(request, request_id):
    sr = get_object_or_404(ServiceRequest, id=request_id)

    if request.user != sr.customer and request.user.role not in ['concierge', 'dealer']:
        return HttpResponseForbidden()

    # Get group members for dropdowns
    concierges = User.objects.filter(role='concierge')
    dealers = User.objects.filter(role='dealer')

    if request.method == 'POST':
        form = EditRequestForm(request.POST, instance=sr, user=request.user)
        if form.is_valid():
            updated = form.save(commit=False)

            status = form.cleaned_data.get('status')
            assigned_to_id = request.POST.get('assigned_to')

            if status == 'Delivery' and request.user.role == 'concierge':
                if assigned_to_id:
                    updated.assigned_to = User.objects.get(id=assigned_to_id)
            elif status == 'In service' and request.user.role == 'dealer':
                if assigned_to_id:
                    updated.assigned_to = User.objects.get(id=assigned_to_id)
            elif status in ['Pending', 'Complete']:
                updated.assigned_to = None  # Clear assignment

            updated.save()
            messages.success(request, "Service request updated.")
            if request.user.role == 'concierge':
                return redirect('concierge_dashboard')
            elif request.user.role == 'dealer':
                return redirect('dealer_dashboard')
            else:
                return redirect('customer_dashboard')
    else:
        form = EditRequestForm(instance=sr, user=request.user)

    return render(request, 'main/edit_service_request.html', {
        'form': form,
        'service_request': sr,
        'concierges': concierges,
        'dealers': dealers
    })

@login_required
def delete_service_request(request, request_id):
    sr = get_object_or_404(ServiceRequest, id=request_id)
    if request.user != sr.customer:
        return HttpResponseForbidden()
    if request.method == 'POST':
        sr.delete()
        messages.success(request, "Service request deleted.")
    return redirect('customer_dashboard')

# --------------------------
# Cars: View / Edit / Delete
# --------------------------
@login_required
def my_cars(request):
    cars = Car.objects.filter(owner=request.user)
    return render(request, 'main/my_cars.html', {'cars': cars})


@login_required
def add_car(request):
    if request.method == 'POST':
        form = AddCarForm(request.POST, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Car added successfully.")
            return redirect('my_cars')
    else:
        form = AddCarForm(user=request.user)
    return render(request, 'main/add_car.html', {'form': form})




@login_required
def delete_car(request, car_id):
    car = get_object_or_404(Car, id=car_id, owner=request.user)
    if request.method == 'POST':
        car.delete()
        messages.success(request, "Car deleted successfully.")
    return redirect('my_cars')

class CarForm(forms.ModelForm):
    class Meta:
        model = Car
        fields = ['model', 'year', 'license_plate']


@login_required
def edit_car(request, car_id):
    car = get_object_or_404(Car, id=car_id, owner=request.user)
    if request.method == 'POST':
        form = CarForm(request.POST, instance=car)
        if form.is_valid():
            form.save()
            messages.success(request, "Car updated successfully.")
            return redirect('my_cars')
    else:
        form = CarForm(instance=car)
    return render(request, 'main/edit_car.html', {'form': form, 'car': car})


# --------------------------
# Account Info
# --------------------------
@login_required
def account_info(request):
    if request.method == 'POST':
        form = AccountUpdateForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Account updated successfully.")
            return redirect('account_info')
    else:
        form = AccountUpdateForm(instance=request.user)
    return render(request, 'main/account.html', {'form': form})


# --------------------------
# Redirect After Login
# --------------------------
@login_required
def redirect_after_login(request):
    role = request.user.role
    if role == 'owner':
        return redirect('owner_dashboard')
    elif role == 'concierge':
        return redirect('concierge_dashboard')
    elif role == 'dealer':
        return redirect('dealer_dashboard')
    else:
        return redirect('customer_dashboard')


# Allow dealer to return to delivery once in service is finished.
@require_POST
def set_request_delivery(request, pk):
    req = get_object_or_404(ServiceRequest, pk=pk, assigned_to=request.user)
    req.status = 'Delivery'
    req.assigned_to = None   # so the concierge can pick it up again
    req.save()
    return redirect('dealer_dashboard')


# Make render health work on free tier. Delete if upgrade on render.com
def health(request):
    return HttpResponse("OK")
