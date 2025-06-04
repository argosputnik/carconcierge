import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_POST, require_GET # Added require_GET
from django.http import HttpResponse, HttpResponseForbidden, Http404, JsonResponse
from django.contrib import messages
from django.utils import timezone
from django.db.models import F, Case, When, Value, CharField
from django.core.paginator import Paginator
from django.urls import reverse # Import reverse for URL generation

from .models import (
    Car,
    ServiceRequest,
    Invoice1,
    Invoice2,
    Dealer,
    Inventory,
    # User is imported via get_user_model()
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

# --------------------------
# Role Checks
# --------------------------
def is_concierge(user):
    return user.is_authenticated and hasattr(user, 'role') and user.role == 'concierge'

def is_dealer(user):
    return user.is_authenticated and hasattr(user, 'role') and user.role == 'dealer'

def owner_only_view(view_func): # Helper decorator from your provided code
    @user_passes_test(lambda u: u.is_authenticated and hasattr(u, 'role') and u.role == 'owner', login_url='home')
    def _wrapped_view(request, *args, **kwargs):
        return view_func(request, *args, **kwargs)
    return _wrapped_view

# --------------------------
# Home & Health
# --------------------------
def home(request):
    return render(request, 'main/home.html')

def health(request):
    return HttpResponse("OK")


# --------------------------
# Signup, Account & Redirect
# --------------------------
def signup_view(request):
    if request.method == 'POST':
        form = CustomSignupForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.role = 'customer'
            user.save()
            customer_group, created = Group.objects.get_or_create(name='Customer') # Ensure group exists
            customer_group.user_set.add(user)
            login(request, user)
            return redirect('customer_dashboard')
    else:
        form = CustomSignupForm()
    return render(request, 'main/signup.html', {'form': form})

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

@login_required
def redirect_after_login(request):
    role = getattr(request.user, 'role', None)
    if role == 'owner':
        return redirect('owner_dashboard')
    if role == 'concierge':
        return redirect('concierge_dashboard')
    if role == 'dealer':
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
    status_filter = request.GET.get('status', 'all')
    user_dealer_profile = getattr(request.user, 'dealer', None)
    if user_dealer_profile:
        open_requests = ServiceRequest.objects.filter(assigned_dealer=user_dealer_profile) \
                                            .exclude(status__in=['Waiting for Payment','Pending', 'Complete'])
    else:
        open_requests = ServiceRequest.objects.none()

    if status_filter != 'all':
        open_requests = open_requests.filter(status=status_filter)

    return render(request, 'main/dealer_dashboard.html', {
        'open_requests': open_requests,
        'status_filter': status_filter,
    })

@login_required
@owner_only_view # Using the decorator from your file
def owner_dashboard(request):
    sort_field_param = request.GET.get('sort', 'requested_at')
    sort_direction = request.GET.get('dir', 'desc')

    valid_sort_fields = {
        'requested_at': 'requested_at',
        'customer': 'customer__username',
        'status': 'status',
        'assigned_to': 'assigned_to__username',
        'description': 'description'
    }
    sort_db_field = valid_sort_fields.get(sort_field_param, 'requested_at')
    sort_prefix = '-' if sort_direction == 'desc' else ''
    final_sort_field = f'{sort_prefix}{sort_db_field}'

    service_requests_list = ServiceRequest.objects.all().order_by(final_sort_field)
    sr_paginator = Paginator(service_requests_list, 5)
    sr_page_number = request.GET.get('sr_page')
    service_requests = sr_paginator.get_page(sr_page_number)

    invoices_list = Invoice1.objects.all().order_by('-invoice_date')
    inv_paginator = Paginator(invoices_list, 5)
    inv_page_number = request.GET.get('inv_page')
    invoices1 = inv_paginator.get_page(inv_page_number)

    context = {
        'service_requests': service_requests,
        'invoices1': invoices1,
        'current_sort': sort_field_param,
        'current_direction': sort_direction,
    }
    return render(request, 'main/owner_dashboard.html', context)


# --------------------------
# Service Requests
# --------------------------
@login_required
def create_service_request(request):
    cars = request.user.cars.all()
    is_locked = (cars.count() == 1)
    missing_info = not request.user.address or not request.user.phone

    if request.method == 'POST':
        if missing_info:
            messages.warning(request, "Please complete your account information before submitting a service request.")
            return redirect('account_info')

        form = ServiceRequestForm(request.POST, user=request.user)
        if form.is_valid():
            car_id = request.POST.get('car')
            car = get_object_or_404(Car, id=car_id, owner=request.user)

            job_type = form.cleaned_data['job_type']
            description = form.cleaned_data['description'] if job_type == 'Other' else job_type

            sr = ServiceRequest.objects.create(
                customer=request.user,
                car=car,
                job_type=job_type,
                description=description,
                pickup_location=form.cleaned_data['pickup_location'],
                dropoff_location=form.cleaned_data['dropoff_location'],
                status='Waiting for Payment'
            )

            Invoice1.objects.create(
                service_request=sr,
                first_name=request.user.first_name or "",
                last_name=request.user.last_name or "",
                address=request.user.address or "",
                email=request.user.email,
                phone=request.user.phone or "",
                invoice_date=sr.requested_at or timezone.now(),
                price="",
                currency="GEL",
                payment_status="Unpaid"
            )
            messages.success(request, "Service request submitted and invoice created.")
            return redirect('customer_dashboard')
    else:
        form = ServiceRequestForm(user=request.user)

    return render(request, 'main/service_request_form.html', {
        'form': form,
        'car_locked': is_locked,
        'locked_plate': cars.first().license_plate if is_locked and cars.exists() else None,
        'missing_info': missing_info,
    })

@login_required
def view_service_request(request, request_id):
    sr = get_object_or_404(ServiceRequest, id=request_id)
    
    # --- Permission Check Logic (Using your existing structure) ---
    allowed_to_view = False
    if request.user == sr.customer:
        allowed_to_view = True
    elif getattr(request.user, 'is_staff', False):
        allowed_to_view = True
    elif hasattr(request.user, 'role'):
        if request.user.role == 'owner':
            allowed_to_view = True
        elif request.user.role == 'concierge' and sr.assigned_to == request.user:
            allowed_to_view = True
        elif request.user.role == 'dealer':
            user_as_dealer_obj = getattr(request.user, 'dealer', None)
            if user_as_dealer_obj and sr.assigned_dealer == user_as_dealer_obj:
                allowed_to_view = True
    
    if not allowed_to_view:
        print(f"FORBIDDEN: User {request.user.username} (Role: {getattr(request.user, 'role', 'N/A')}) tried to access SR#{sr.id}.", flush=True)
        return HttpResponseForbidden("You do not have permission to view this service request.")

    location_api_url = None
    if sr.assigned_to and sr.share_location and sr.status in ['Pending', 'In service', 'Delivery']:
        try:
            # --- THIS IS THE CORRECTED LINE ---
            location_api_url = reverse('service_request_location', kwargs={'request_id': sr.id}) 
        except NoReverseMatch:
            print(f"ERROR: NoReverseMatch for 'service_request_location' with request_id {sr.id}", flush=True)
            location_api_url = None 

    dealer_address = None
    dealer_name = None
    if sr.status == 'In service' and sr.assigned_dealer:
        if hasattr(sr.assigned_dealer, 'address') and sr.assigned_dealer.address:
            dealer_address = sr.assigned_dealer.address
            dealer_name = sr.assigned_dealer.name
        else:
            print(f"DEBUG: SR#{sr.id} is 'In service' and has assigned_dealer, but dealer has no address or address attribute is empty.", flush=True)
    
    # --- DETAILED DEBUG BLOCK (GENERALIZED) ---
    print(f"VIEW_CONTEXT DEBUG FOR SR#{sr.id}:", flush=True)
    print(f"  Service Request Status: {sr.status}", flush=True)
    print(f"  Pickup Location: {sr.pickup_location}", flush=True)
    print(f"  Share Location: {sr.share_location}", flush=True)
    if sr.assigned_to:
        print(f"  Assigned To (Concierge): User object: {repr(sr.assigned_to)}, ID: {sr.assigned_to.id}, Username: {sr.assigned_to.username}", flush=True)
    else:
        print(f"  Assigned To (Concierge): None", flush=True)
    if sr.assigned_dealer:
        print(f"  Assigned Dealer: Dealer object: {repr(sr.assigned_dealer)}, ID: {sr.assigned_dealer.id}, Name: {sr.assigned_dealer.name}, Address: {getattr(sr.assigned_dealer, 'address', 'N/A')}", flush=True)
    else:
        print(f"  Assigned Dealer: None", flush=True)
    print(f"  Location API URL to be passed: {location_api_url}", flush=True)
    print(f"  Dealer Address to be passed: {dealer_address}", flush=True)
    print(f"  Dealer Name to be passed: {dealer_name}", flush=True)
    # --- END DETAILED DEBUG BLOCK ---

    can_edit = False
    if request.user == sr.customer:
        can_edit = True
    elif hasattr(request.user, 'role') and request.user.role in ['concierge', 'dealer', 'owner']:
        can_edit = True
    elif getattr(request.user, 'is_staff', False):
        can_edit = True

    return render(request, 'main/view_service_request.html', {
        'service_request': sr,
        'location_api_url': location_api_url,
        'can_edit': can_edit,
        'dealer_address': dealer_address,
        'dealer_name': dealer_name,
    })

@login_required
def edit_service_request(request, request_id):
    sr = get_object_or_404(ServiceRequest, id=request_id)
    if (
        request.user != sr.customer
        and not (hasattr(request.user, 'role') and request.user.role in ['concierge','dealer','owner'])
        and not getattr(request.user, 'is_staff', False)
    ):
        return HttpResponseForbidden("No permission to edit this request.")

    can_edit_locations = (
        request.user == sr.customer or (hasattr(request.user, 'role') and request.user.role == 'owner')
    )

    if request.method == 'POST':
        form = EditRequestForm(request.POST, instance=sr, user=request.user)
        if form.is_valid():
            updated_sr = form.save(commit=False)
            new_status = form.cleaned_data.get('status')
            new_assigned_to = form.cleaned_data.get('assigned_to')
            new_assigned_dealer = form.cleaned_data.get('assigned_dealer')
            updated_sr.status = new_status

            if request.user.role == 'concierge' and updated_sr.assigned_to == request.user:
                if new_status == 'Delivery':
                    concierge_latitude = request.POST.get('concierge_latitude')
                    concierge_longitude = request.POST.get('concierge_longitude')
                    if concierge_latitude and concierge_longitude:
                        try:
                            updated_sr.concierge_latitude = float(concierge_latitude)
                            updated_sr.concierge_longitude = float(concierge_longitude)
                            updated_sr.share_location = True
                        except ValueError:
                            messages.warning(request, "Invalid location data format.")
                            updated_sr.share_location = False
                    else:
                        messages.warning(request, "Location data missing for delivery status.")
                        updated_sr.share_location = False
                else:
                    updated_sr.share_location = False
            elif updated_sr.assigned_to != request.user and sr.assigned_to == request.user:
                updated_sr.share_location = False

            if request.user.role in ['owner', 'concierge']:
                updated_sr.assigned_to = new_assigned_to
            if request.user.role in ['owner', 'concierge']:
                updated_sr.assigned_dealer = new_assigned_dealer
            if new_status != 'Delivery' or not updated_sr.assigned_to or (hasattr(updated_sr.assigned_to, 'role') and updated_sr.assigned_to.role != 'concierge'):
                 if updated_sr.share_location: # Only turn off if it was on
                    updated_sr.share_location = False
            
            updated_sr.save()
            messages.success(request, "Service request updated.")
            
            if hasattr(request.user, 'role'):
                if request.user.role == 'customer': return redirect('customer_dashboard')
                if request.user.role == 'concierge': return redirect('concierge_dashboard')
                if request.user.role == 'dealer': return redirect('dealer_dashboard')
                if request.user.role == 'owner': return redirect('owner_dashboard')
            return redirect('home')
    else:
        form = EditRequestForm(instance=sr, user=request.user)

    context = {
        'form': form,
        'service_request': sr,
        'can_edit_locations': can_edit_locations,
        'current_user_role': getattr(request.user, 'role', None),
        'assigned_user_id': sr.assigned_to.id if sr.assigned_to else '',
        'current_user_id': request.user.id,
    }
    return render(request, 'main/edit_service_request.html', context)

@login_required
def delete_service_request(request, request_id):
    sr = get_object_or_404(ServiceRequest, id=request_id)
    if not (request.user == sr.customer or (hasattr(request.user, 'role') and request.user.role == 'owner')):
        return HttpResponseForbidden("No permission to delete this request.")
    if request.method == 'POST':
        sr.delete()
        messages.success(request, "Service request deleted.")
        return redirect('customer_dashboard')
    return render(request, 'main/delete_service_request.html', {'service_request': sr})

@require_POST
@login_required
@user_passes_test(is_dealer)
def set_request_delivery(request, pk):
    service_request_id = pk 
    print(f"[SET_REQUEST_DELIVERY] Called for SR PK={service_request_id} by user: {request.user.username} (ID: {request.user.id}, Role: {getattr(request.user, 'role', 'N/A')})", flush=True)
    try:
        user_as_dealer_obj = getattr(request.user, 'dealer', None)
        if not user_as_dealer_obj:
            messages.error(request, "User account is not associated with a dealership.")
            print(f"  [SET_REQUEST_DELIVERY] User {request.user.username} not associated with a dealer.", flush=True)
            return redirect('dealer_dashboard')

        sr = get_object_or_404(
            ServiceRequest,
            pk=service_request_id,
            assigned_dealer=user_as_dealer_obj,
            status='In service'
        )
        
        previous_concierge_username = "None"
        if sr.assigned_to:
            print(f"  [SET_REQUEST_DELIVERY] SR#{sr.id} found. Current concierge: {repr(sr.assigned_to)} (ID: {sr.assigned_to.id}, Username: {sr.assigned_to.username})", flush=True)
            previous_concierge_username = sr.assigned_to.username
        else:
            print(f"  [SET_REQUEST_DELIVERY] SR#{sr.id} found, but no concierge was assigned.", flush=True)
            # messages.warning(request, f"Service Request #{sr.id} has no concierge currently assigned. Setting to Delivery anyway.") # Already handled by print

        sr.status = 'Delivery'
        sr.assigned_to = None
        sr.share_location = False
        sr.save()

        print(f"  [SET_REQUEST_DELIVERY] SR#{sr.id} status updated to 'Delivery'. Concierge '{previous_concierge_username}' unassigned.", flush=True)
        messages.success(request, f"Service Request #{sr.id} status updated to Delivery. Concierge unassigned.")
    except ServiceRequest.DoesNotExist:
        print(f"  [SET_REQUEST_DELIVERY] SR PK={service_request_id} not found for dealer '{request.user.username}' (Dealer Obj: {user_as_dealer_obj}) or not in 'In service' status.", flush=True)
        messages.error(request, f"Service Request #{service_request_id} could not be updated.")
    except Exception as e:
        print(f"  [SET_REQUEST_DELIVERY] Unexpected error processing SR PK={service_request_id}: {e}", flush=True)
        messages.error(request, f"An unexpected error occurred.")
    return redirect('dealer_dashboard')


# --------------------------
# Car Management
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
            car = form.save(commit=False)
            car.owner = request.user
            car.save()
            messages.success(request, "Car added successfully.")
            return redirect('my_cars')
    else:
        form = AddCarForm(user=request.user)
    return render(request, 'main/add_car.html', {'form': form})

@login_required
def edit_car(request, car_id):
    car = get_object_or_404(Car, id=car_id, owner=request.user)
    if request.method == 'POST':
        form = CarForm(request.POST, instance=car)
        if form.is_valid():
            updated_car = form.save(commit=False)
            updated_car.license_plate = updated_car.license_plate.upper()
            updated_car.save()
            messages.success(request, "Car updated successfully.")
            return redirect('my_cars')
    else:
        form = CarForm(instance=car)
    return render(request, 'main/edit_car.html', {'form': form, 'car': car})

@login_required
def delete_car(request, car_id):
    car = get_object_or_404(Car, id=car_id, owner=request.user)
    if request.method == 'POST':
        car.delete()
        messages.success(request, "Car deleted successfully.")
        return redirect('my_cars')
    return render(request, 'main/delete_car.html', {'car': car})


# --------------------------
# Owner / Dealer / Concierge Management
# --------------------------
@login_required
@owner_only_view
def view_owners(request):
    owners = User.objects.filter(role='owner')
    return render(request, 'main/view_owners.html', {'owners': owners})

@login_required
@owner_only_view
def add_owner(request):
    if request.method == 'POST':
        form = AddOwnerForm(request.POST)
        if form.is_valid():
            new_owner = form.save(commit=False)
            new_owner.is_staff = True
            new_owner.role = 'owner'
            new_owner.save()
            owner_group, created = Group.objects.get_or_create(name='Owners')
            owner_group.user_set.add(new_owner)
            messages.success(request, "Owner created.")
            return redirect('owner_dashboard')
    else:
        form = AddOwnerForm()
    return render(request, 'main/add_owner.html', {'form': form})

@login_required
@owner_only_view
def delete_owner(request, owner_id):
    owner_to_delete = get_object_or_404(User, id=owner_id, role='owner')
    if request.user == owner_to_delete:
        messages.error(request, "You cannot delete your own owner account.")
        return redirect('view_owners')
    if request.method == 'POST':
        owner_to_delete.delete()
        messages.success(request, "Owner deleted.")
    return redirect('view_owners')


@login_required
@owner_only_view
def view_dealers(request):
    dealers = Dealer.objects.select_related('user').all()
    return render(request, 'main/view_dealers.html', {'dealers': dealers})

@login_required
@owner_only_view
def add_dealer(request):
    if request.method == 'POST':
        form = AddDealerForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.role = 'dealer'
            user.is_staff = True
            user.save()
            dealer_group, created = Group.objects.get_or_create(name='Dealers')
            dealer_group.user_set.add(user)

            Dealer.objects.create(
                user=user,
                name=form.cleaned_data.get('dealer_name', f"{user.first_name} {user.last_name}".strip()),
                phone=form.cleaned_data.get('phone', user.phone),
                address=form.cleaned_data.get('address', user.address),
                job_specialty=form.cleaned_data.get('job_specialty', [])
            )
            messages.success(request, "Dealer added.")
            return redirect('view_dealers')
    else:
        form = AddDealerForm()
    return render(request, 'main/add_dealer.html', {'form': form})

@login_required
@owner_only_view
def edit_dealer(request, dealer_id):
    dealer = get_object_or_404(Dealer, id=dealer_id)
    if request.method == 'POST':
        form = EditDealerForm(request.POST, instance=dealer)
        if form.is_valid():
            form.save()
            messages.success(request, "Dealer updated.")
            return redirect('view_dealers')
    else:
        form = EditDealerForm(instance=dealer)
    return render(request, 'main/edit_dealer.html', {'form': form, 'dealer': dealer})

@login_required
@owner_only_view
def delete_dealer(request, dealer_id):
    dealer = get_object_or_404(Dealer, id=dealer_id)
    if request.method == 'POST':
        if dealer.user:
            dealer.user.delete()
        else:
            dealer.delete()
        messages.success(request, "Dealer and associated user account deleted.")
        return redirect('view_dealers')
    return render(request, 'main/delete_dealer.html', {'dealer': dealer})


@login_required
@owner_only_view
def view_concierges(request):
    concierges = User.objects.filter(role='concierge')
    return render(request, 'main/view_concierges.html', {'concierges': concierges})

@login_required
@owner_only_view
def add_concierge(request):
    if request.method == 'POST':
        form = AddConciergeForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.role = 'concierge'
            user.is_staff = False
            user.save()
            concierge_group, created = Group.objects.get_or_create(name='Concierge')
            concierge_group.user_set.add(user)
            messages.success(request, "Concierge added.")
            return redirect('view_concierges')
    else:
        form = AddConciergeForm()
    return render(request, 'main/add_concierge.html', {'form': form})

@login_required
@owner_only_view
def edit_concierge(request, concierge_id):
    concierge = get_object_or_404(User, id=concierge_id, role='concierge')
    if request.method == 'POST':
        form = EditConciergeForm(request.POST, instance=concierge)
        if form.is_valid():
            form.save()
            messages.success(request, "Concierge updated.")
            return redirect('view_concierges')
    else:
        form = EditConciergeForm(instance=concierge)
    return render(request, 'main/edit_concierge.html', {'form': form, 'concierge': concierge})

@login_required
@owner_only_view
def delete_concierge(request, concierge_id):
    concierge = get_object_or_404(User, id=concierge_id, role='concierge')
    if request.method == 'POST':
        concierge.delete()
        messages.success(request, "Concierge deleted.")
        return redirect('view_concierges')
    return render(request, 'main/delete_concierge.html', {'concierge': concierge})


# --------------------------
# Invoices
# --------------------------
@login_required
def view_invoice(request, invoice_type, invoice_id):
    invoice_obj = None
    template_name = 'main/view_invoice.html'
    
    if invoice_type == 1:
        invoice_obj = get_object_or_404(Invoice1, id=invoice_id)
        if not (request.user == invoice_obj.service_request.customer or \
                (hasattr(request.user, 'role') and request.user.role == 'owner')):
            return HttpResponseForbidden("You do not have permission to view this invoice.")
    elif invoice_type == 2:
        invoice_obj = get_object_or_404(Invoice2, id=invoice_id)
        if not (hasattr(request.user, 'role') and request.user.role in ['owner', 'dealer']):
            return HttpResponseForbidden("You do not have permission to view this invoice.")
    else:
        raise Http404("Invalid invoice type specified.")
        
    return render(request, template_name, {
        'invoice': invoice_obj,
        'invoice_type': invoice_type
    })

@login_required
@owner_only_view
def edit_invoice(request, invoice_id):
    invoice1 = Invoice1.objects.filter(id=invoice_id).first()
    invoice2 = Invoice2.objects.filter(id=invoice_id).first()
    invoice_obj = invoice1 or invoice2

    if not invoice_obj:
        messages.error(request, "Invoice not found.")
        return redirect("owner_dashboard")

    InvoiceFormClass = Invoice1Form if isinstance(invoice_obj, Invoice1) else Invoice2Form

    if request.method == "POST":
        form = InvoiceFormClass(request.POST, instance=invoice_obj)
        if form.is_valid():
            old_payment_status = invoice_obj.payment_status
            updated_invoice = form.save(commit=False)
            updated_invoice.updated_at = timezone.now()
            updated_invoice.save()
            # form.save_m2m() # Only if form has m2m fields

            if invoice_obj.service_request and old_payment_status != 'Paid' and updated_invoice.payment_status == 'Paid':
                if invoice_obj.service_request.status == 'Waiting for Payment':
                    invoice_obj.service_request.status = 'Pending'
                    invoice_obj.service_request.save()
                    messages.info(request, f"Service Request #{invoice_obj.service_request.id} status updated to Pending.")
            
            messages.success(request, "Invoice updated successfully.")
            return redirect("owner_dashboard")
    else:
        form = InvoiceFormClass(instance=invoice_obj)
    
    return render(request, "main/edit_invoice.html", {
        "form": form,
        "invoice": invoice_obj,
        "invoice_type": 1 if isinstance(invoice_obj, Invoice1) else 2
    })


# --------------------------
# Inventory (Owner only)
# --------------------------
@login_required
@owner_only_view
def view_inventory(request):
    items = Inventory.objects.all()
    return render(request, 'main/view_inventory.html', {'inventory': items})

@login_required
@owner_only_view
def add_inventory(request):
    if request.method == 'POST':
        form = AddInventoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Inventory item added.")
            return redirect('view_inventory')
    else:
        form = AddInventoryForm()
    return render(request, 'main/add_inventory.html', {'form': form})

@login_required
@owner_only_view
def edit_inventory(request, inventory_id):
    item = get_object_or_404(Inventory, id=inventory_id)
    if request.method == 'POST':
        form = EditInventoryForm(request.POST, instance=item)
        if form.is_valid():
            form.save()
            messages.success(request, "Inventory updated.")
            return redirect('view_inventory')
    else:
        form = EditInventoryForm(instance=item)
    return render(request, 'main/edit_inventory.html', {
        'form': form,
        'item': item
    })

@require_POST
@login_required
@owner_only_view
def delete_inventory(request, item_id):
    try:
        item = get_object_or_404(Inventory, id=item_id)
        if item.item_quantity > 1 and request.POST.get('action') == 'decrement':
            item.item_quantity -= 1
            item.save()
            return JsonResponse({'status':'decremented','new_quantity':item.item_quantity, 'message': 'Quantity decremented.'})
        else:
            item_name = item.item_name
            item.delete()
            return JsonResponse({'status':'deleted', 'message': f'Item "{item_name}" deleted.'})
    except Http404:
        return JsonResponse({'status':'error','message':'Item not found.'}, status=404)
    except Exception as e:
        return JsonResponse({'status':'error','message':f'An error occurred: {str(e)}'}, status=500)


# --------------------------
# Real-time Location Updates (Concierge Location API)
# --------------------------

# Endpoint for concierges to update their location (POST)
@require_POST
@login_required
@user_passes_test(is_concierge)
def update_concierge_location(request, request_id):
    print(f"[API update_concierge_location for SR#{request_id}] Called by concierge: {request.user.username}", flush=True)
    try:
        sr = get_object_or_404(
            ServiceRequest,
            id=request_id,
            assigned_to=request.user,
            status='Delivery'
        )
    except Http404:
        print(f"  [API update_concierge_location SR#{request_id}] ServiceRequest not found, not assigned to user, or not in Delivery status.", flush=True)
        return JsonResponse({'status': 'error', 'message': 'Service request not found, not assigned to you, or not in Delivery status.'}, status=404)

    if not sr.share_location:
        print(f"  [API update_concierge_location SR#{request_id}] Location sharing is not enabled.", flush=True)
        return JsonResponse({'status': 'error', 'message': 'Location sharing is not enabled for this request.'}, status=403)

    try:
        data = json.loads(request.body)
        latitude = data.get('lat')
        longitude = data.get('lng')
        print(f"  [API update_concierge_location SR#{request_id}] Received data: lat={latitude}, lng={longitude}", flush=True)

        if latitude is not None and longitude is not None:
            try:
                sr.concierge_latitude = float(latitude)
                sr.concierge_longitude = float(longitude)
                sr.save(update_fields=['concierge_latitude', 'concierge_longitude', 'last_updated'])
                print(f"  [API update_concierge_location SR#{request_id}] Location saved to DB: lat={sr.concierge_latitude}, lng={sr.concierge_longitude}", flush=True)
                return JsonResponse({'status': 'success', 'message': 'Location updated successfully.'})
            except ValueError:
                print(f"  [API update_concierge_location SR#{request_id}] Invalid location data format (lat/lng not float).", flush=True)
                return JsonResponse({'status': 'error', 'message': 'Invalid location data format.'}, status=400)
        else:
            print(f"  [API update_concierge_location SR#{request_id}] Missing lat or lng in request body.", flush=True)
            return JsonResponse({'status': 'error', 'message': 'Missing latitude or longitude in request data.'}, status=400)
    except json.JSONDecodeError:
        print(f"  [API update_concierge_location SR#{request_id}] Invalid JSON in request body.", flush=True)
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON format.'}, status=400)
    except Exception as e:
        print(f"  [API update_concierge_location SR#{request_id}] Unexpected error: {str(e)}", flush=True)
        return JsonResponse({'status': 'error', 'message': f'An unexpected server error occurred: {str(e)}'}, status=500)

# Endpoint for map to fetch concierge location (GET)
@require_GET # Ensure this view only responds to GET requests
@login_required 
def service_request_location(request, request_id):
    print(f"[API service_request_location for SR#{request_id}] Called by user: {request.user.username if request.user.is_authenticated else 'Anonymous'}.", flush=True)
    
    try:
        sr = get_object_or_404(ServiceRequest, id=request_id)
        print(f"  [API SR#{request_id}] ServiceRequest object found. Status: {sr.status}, Share location: {sr.share_location}, Assigned to: {sr.assigned_to.username if sr.assigned_to else 'None'}.", flush=True)
    except Http404:
        print(f"  [API SR#{request_id}] ServiceRequest.DoesNotExist. Returning 404.", flush=True)
        return JsonResponse({'status': 'error', 'message': 'Service request not found.'}, status=404)

    can_view_location = False
    if request.user == sr.customer:
        can_view_location = True
    elif getattr(request.user, 'is_staff', False):
        can_view_location = True
    elif hasattr(request.user, 'role'):
        if request.user.role == 'owner':
            can_view_location = True
        elif request.user.role == 'concierge' and sr.assigned_to == request.user:
            can_view_location = True

    if not can_view_location:
        print(f"  [API SR#{request_id}] User {request.user.username} not permitted to view this location. Returning 403.", flush=True)
        return JsonResponse({'status': 'error', 'message': 'Permission denied to view location.'}, status=403)

    if not sr.share_location or sr.assigned_to is None or sr.status not in ['Pending', 'In service', 'Delivery']:
        reason = ""
        if not sr.share_location: reason += "Sharing disabled. "
        if sr.assigned_to is None: reason += "No concierge assigned. "
        if sr.status not in ['Pending', 'In service', 'Delivery']: reason += f"Status is '{sr.status}', not suitable for live tracking."
        print(f"  [API SR#{request_id}] Location not actively shared. Reason: {reason.strip()} Returning 404.", flush=True)
        return JsonResponse({'status': 'location_not_available', 'message': f'Location not actively shared. {reason.strip()}'}, status=404)

    lat = sr.concierge_latitude
    lng = sr.concierge_longitude

    print(f"  [API SR#{request_id}] Fetched from DB - Lat: {lat}, Lng: {lng}", flush=True)

    if lat is not None and lng is not None:
        print(f"  [API SR#{request_id}] Returning Lat: {lat}, Lng: {lng}", flush=True)
        return JsonResponse({'lat': lat, 'lng': lng})
    else:
        print(f"  [API SR#{request_id}] Lat/Lng is None in DB for concierge. Returning 404.", flush=True)
        return JsonResponse({'status': 'location_data_missing', 'message': 'Concierge location data not yet recorded.'}, status=404)

# Note: The duplicate service_request_location function that was at the very end
# of the previously provided file has been removed, keeping the one above which includes
# more detailed logging and permission checks.