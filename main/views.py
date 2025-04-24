import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import HttpResponseForbidden, Http404, JsonResponse, HttpResponse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import (
    Car,
    ServiceRequest,
    Invoice1,
    Invoice2,
    Dealer,
    Inventory,
)
from .forms import (
    CustomSignupForm,
    ServiceRequestForm,
    EditRequestForm,
    CarForm,
    AddCarForm,
    AccountUpdateForm,
    AddOwnerForm,
    AddDealerForm,
    AddConciergeForm,
    EditDealerForm,
    EditConciergeForm,
    AddInventoryForm,
    EditInventoryForm,
    Invoice1Form,
    Invoice2Form,
)

User = get_user_model()


# --------------------
# View concierge list
# --------------------
@login_required
def view_concierges(request):
    concierges = User.objects.filter(role='concierge')
    return render(request, 'main/view_concierges.html', {
        'concierges': concierges
    })


# --------------------------
# Home View
# --------------------------
def home(request):
    return render(request, 'main/home.html')


# --------------------------
# Role Checks
# --------------------------
def is_concierge(user):
    return user.is_authenticated and user.role == 'concierge'


def is_dealer(user):
    return user.is_authenticated and user.role == 'dealer'


# --------------------------
# Signup View
# --------------------------
def signup_view(request):
    if request.method == 'POST':
        form = CustomSignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            Group.objects.get_or_create(name='Customer')[0].user_set.add(user)
            login(request, user)
            return redirect('customer_dashboard')
    else:
        form = CustomSignupForm()
    return render(request, 'main/signup.html', {'form': form})


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
    return redirect('customer_dashboard')


# --------------------------
# Dashboards
# --------------------------
@login_required
def customer_dashboard(request):
    status_filter = request.GET.get('status', 'all')
    service_requests = ServiceRequest.objects.filter(customer=request.user)
    if status_filter != 'all':
        service_requests = service_requests.filter(status=status_filter)
    invoices = Invoice1.objects.filter(
        service_request__customer=request.user
    ).order_by('payment_status', '-invoice_date')
    return render(request, 'main/customer_dashboard.html', {
        'open_requests': service_requests,
        'status_filter': status_filter,
        'invoices': invoices,
    })


@login_required
@user_passes_test(is_concierge)
def concierge_dashboard(request):
    status_filter = request.GET.get('status', 'all')
    open_requests = ServiceRequest.objects.exclude(status='Waiting for Payment')
    if status_filter != 'all':
        open_requests = open_requests.filter(status=status_filter)
    return render(request, 'main/concierge_dashboard.html', {
        'open_requests': open_requests,
        'status_filter': status_filter,
    })


@login_required
@user_passes_test(is_dealer)
def dealer_dashboard(request):
    # only "In Service" requests assigned to this dealer
    open_requests = ServiceRequest.objects.filter(
        status='In Service',
        assigned_to=request.user
    ).order_by('-requested_at')
    return render(request, 'main/dealer_dashboard.html', {
        'open_requests': open_requests,
        'open_request_count': open_requests.count(),
    })


@login_required
def owner_dashboard(request):
    service_requests = ServiceRequest.objects.all()
    invoices1 = Invoice1.objects.all()
    invoices2 = Invoice2.objects.all()
    return render(request, 'main/owner_dashboard.html', {
        'service_requests': service_requests,
        'invoices1': invoices1,
        'invoices2': invoices2,
    })


# -----------------------
# Service Requests
# -----------------------
@login_required
def create_service_request(request):
    cars = request.user.cars.all()
    is_locked = (cars.count() == 1)
    missing_info = not request.user.address or not request.user.phone

    if request.method == 'POST':
        if missing_info:
            messages.warning(
                request,
                "Please complete your account information before submitting a service request."
            )
            return redirect('account_info')

        form = ServiceRequestForm(request.POST, user=request.user)
        if form.is_valid():
            car = get_object_or_404(
                Car,
                id=request.POST.get('car'),
                owner=request.user
            )
            if not car.model:
                car.model = form.cleaned_data['model']
            if not car.year:
                car.year = form.cleaned_data['year']
            car.save()

            job_type = form.cleaned_data['job_type']
            description = (
                form.cleaned_data['description']
                if job_type == 'Other'
                else job_type
            )

            sr = ServiceRequest.objects.create(
                customer=request.user,
                car=car,
                job_type=job_type,
                description=description,
                pickup_location=form.cleaned_data['pickup_location'],
                dropoff_location=form.cleaned_data['dropoff_location'],
            )

            Invoice1.objects.create(
                service_request=sr,
                first_name=request.user.first_name,
                last_name=request.user.last_name,
                address=request.user.address,
                email=request.user.email,
                phone=request.user.phone,
                invoice_date=sr.requested_at or timezone.now(),
                price="",
                currency="GEL",
                payment_status="Unpaid"
            )

            messages.success(request, "Service request submitted.")
            return redirect('customer_dashboard')
    else:
        try:
            default_car = cars.get(license_plate__iexact=request.user.username)
            initial = {'model': default_car.model, 'year': default_car.year}
        except Car.DoesNotExist:
            initial = {}
        form = ServiceRequestForm(user=request.user, initial=initial)

    return render(request, 'main/service_request_form.html', {
        'form': form,
        'car_locked': is_locked,
        'locked_plate': cars.first().license_plate if is_locked else None,
        'missing_info': missing_info,
    })


# ... all other views unchanged ...


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
