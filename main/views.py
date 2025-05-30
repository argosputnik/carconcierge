import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_POST, require_GET
from django.http import HttpResponse, HttpResponseForbidden, Http404, JsonResponse, HttpResponseServerError
from django.contrib import messages
from django.utils import timezone
from django.core.paginator import Paginator
from django.urls import reverse

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

# --------------------------
# Role Checks
# --------------------------
def is_concierge(user):
    return user.is_authenticated and user.role == 'concierge'

def is_dealer(user):
    return user.is_authenticated and user.role == 'dealer'

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
            Group.objects.get_or_create(name='Customer')[0].user_set.add(user)
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
    role = request.user.role
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
    open_requests = ServiceRequest.objects.filter(assigned_to=request.user) \
                                        .exclude(status__in=['Waiting for Payment','Pending'])
    if status_filter != 'all':
        open_requests = open_requests.filter(status=status_filter)
    return render(request, 'main/dealer_dashboard.html', {
        'open_requests': open_requests,
        'status_filter': status_filter,
    })

@login_required
def owner_dashboard(request):
    sort_field = request.GET.get('sort', 'requested_at')
    sort_direction = request.GET.get('dir', 'desc')
    valid_sort_fields = {
        'requested_at': 'requested_at',
        'customer': 'customer__first_name',
        'status': 'status',
        'assigned_to': 'assigned_to__first_name',
        'description': 'description'
    }
    sort_field = valid_sort_fields.get(sort_field, 'requested_at')
    if sort_direction == 'asc':
        sort_field = sort_field
    else:
        sort_field = f'-{sort_field}'
    service_requests_list = ServiceRequest.objects.all().order_by(sort_field)
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
        'current_sort': sort_field.lstrip('-'),
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
            messages.warning(
                request,
                "Please complete your account information before submitting a service request."
            )
            return redirect('account_info')
        form = ServiceRequestForm(request.POST, user=request.user)
        if form.is_valid():
            car = get_object_or_404(Car, id=request.POST.get('car'), owner=request.user)
            job_type = form.cleaned_data['job_type']
            description = form.cleaned_data['description'] if job_type == 'Other' else job_type
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
        form = ServiceRequestForm(user=request.user)
    return render(request, 'main/service_request_form.html', {
        'form': form,
        'car_locked': is_locked,
        'locked_plate': cars.first().license_plate if is_locked else None,
        'missing_info': missing_info,
    })

@login_required
def view_service_request(request, request_id):
    sr = get_object_or_404(ServiceRequest, id=request_id)
    # ... permission checks ...

    location_api_url = None
    if sr.assigned_to and sr.share_location:
        location_api_url = reverse('service_request_location', kwargs={'request_id': sr.id})

    # Only show dealer marker if status is "In service" and assigned_to is set
    dealer_address = None
    dealer_name = None
    if sr.status == 'In service' and sr.assigned_to and sr.assigned_dealer:
        dealer_address = sr.assigned_dealer.address
        dealer_name = sr.assigned_dealer.name
        print(f"DEBUG: Dealer address for SR#{sr.id}: {dealer_address} (name: {dealer_name})")
    else:
        print(f"DEBUG: No dealer marker for SR#{sr.id} (status: {sr.status}, assigned_to: {sr.assigned_to}, assigned_dealer: {sr.assigned_dealer})")

    return render(request, 'main/view_service_request.html', {
        'service_request': sr,
        'location_api_url': location_api_url,
        'can_edit': (request.user == sr.customer or request.user.role in ['concierge', 'dealer', 'owner']),
        'dealer_address': dealer_address,
        'dealer_name': dealer_name,
    })


@login_required
def edit_service_request(request, request_id):
    sr = get_object_or_404(ServiceRequest, id=request_id)
    if (
        request.user != sr.customer
        and request.user.role not in ['concierge','dealer','owner']
    ):
        return HttpResponseForbidden("No permission to view or edit this request.")
    can_edit_locations = (
        request.user == sr.customer or request.user.role == 'owner'
    )
    if request.method == 'POST':
        form = EditRequestForm(request.POST, instance=sr, user=request.user)
        if form.is_valid():
            updated = form.save(commit=False)
            status = form.cleaned_data['status']
            assigned_to = form.cleaned_data.get('assigned_to')
            if request.user.role == 'concierge':
                is_now_assigned_to_current_concierge = updated.assigned_to == request.user
                was_assigned_to_current_concierge = sr.assigned_to == request.user
                if status == 'Delivery' and (is_now_assigned_to_current_concierge or was_assigned_to_current_concierge):
                    concierge_latitude_str = request.POST.get('concierge_latitude')
                    concierge_longitude_str = request.POST.get('concierge_longitude')
                    try:
                        concierge_latitude = float(concierge_latitude_str) if concierge_latitude_str else None
                        concierge_longitude = float(concierge_longitude_str) if concierge_longitude_str else None
                        if concierge_latitude is not None and concierge_longitude is not None:
                            updated.concierge_latitude = concierge_latitude
                            updated.concierge_longitude = concierge_longitude
                            updated.share_location = True
                        else:
                            messages.warning(request, "Could not get your current location. Location sharing may not be active.")
                            updated.share_location = False
                    except (ValueError, TypeError):
                        messages.error(request, "Invalid location data received.")
                        updated.share_location = False
                elif sr.status == 'Delivery' and status != 'Delivery' and sr.assigned_to == request.user:
                    updated.share_location = False
            if status in ['Complete', 'Cancelled']:
                updated.assigned_to = None
                updated.share_location = False
            elif request.user.role != 'concierge' and status != 'Delivery':
                updated.share_location = False
            updated.save()
            messages.success(request, "Service request updated.")
            if request.user.role == 'customer':
                return redirect('customer_dashboard')
            elif request.user.role == 'concierge':
                return redirect('concierge_dashboard')
            elif request.user.role == 'dealer':
                return redirect('dealer_dashboard')
            elif request.user.role == 'owner':
                return redirect('owner_dashboard')
            else:
                return redirect('home')
    else:
        form = EditRequestForm(instance=sr, user=request.user)
    context = {
        'form': form,
        'service_request': sr,
        'can_edit_locations': can_edit_locations,
        'current_user_role': request.user.role,
        'assigned_user_id': sr.assigned_to.id if sr.assigned_to else '',
        'current_user_id': request.user.id,
    }
    return render(request, 'main/edit_service_request.html', context)

@login_required
def delete_service_request(request, request_id):
    sr = get_object_or_404(ServiceRequest, id=request_id)
    if (
        request.user != sr.customer
        and request.user.role not in ['concierge','dealer','owner']
    ):
        return HttpResponseForbidden("No permission to delete.")
    if request.method == 'POST':
        sr.delete()
        messages.success(request, "Service request deleted.")
        return redirect('customer_dashboard')
    return render(request, 'main/delete_service_request.html', {'service_request': sr})

@require_POST
@login_required
@user_passes_test(is_dealer)
def set_request_delivery(request, pk):
    sr = get_object_or_404(
        ServiceRequest,
        pk=pk,
        assigned_to=request.user,
        status__in=['In service']
    )
    sr.status = 'Delivery'
    sr.assigned_to = None
    sr.share_location = False
    sr.save()
    messages.success(request, f"Service Request #{sr.id} status updated to Delivery.")
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
            form.save()
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
            updated = form.save(commit=False)
            updated.license_plate = updated.license_plate.upper()
            updated.save()
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
def view_owners(request):
    if request.user.role != 'owner':
        return HttpResponseForbidden("You do not have permission to view this page.")
    owners = User.objects.filter(role='owner')
    return render(request, 'main/view_owners.html', {'owners': owners})

@login_required
def add_owner(request):
    if request.user.role != 'owner':
        return HttpResponseForbidden("You do not have permission to add owners.")
    if request.method == 'POST':
        form = AddOwnerForm(request.POST)
        if form.is_valid():
            new_owner = form.save(commit=False)
            new_owner.is_staff = True
            new_owner.role = 'owner'
            new_owner.save()
            Group.objects.get_or_create(name='Owners')[0].user_set.add(new_owner)
            messages.success(request, "Owner created.")
            return redirect('owner_dashboard')
    else:
        form = AddOwnerForm()
    return render(request, 'main/add_owner.html', {'form': form})

@login_required
def delete_owner(request, owner_id):
    if request.user.role != 'owner':
        return HttpResponseForbidden("You do not have permission to delete owners.")
    owner = get_object_or_404(User, id=owner_id, role='owner')
    if request.user == owner:
        messages.error(request, "You cannot delete your own owner account.")
        return redirect('view_owners')
    if request.method == 'POST':
        owner.delete()
        messages.success(request, "Owner deleted.")
    return redirect('view_owners')

@login_required
def view_dealers(request):
    if request.user.role != 'owner':
        return HttpResponseForbidden("You do not have permission to view this page.")
    dealers = Dealer.objects.select_related('user').all()
    return render(request, 'main/view_dealers.html', {'dealers': dealers})

@login_required
def add_dealer(request):
    if request.user.role != 'owner':
        return HttpResponseForbidden("You do not have permission to add dealers.")
    if request.method == 'POST':
        form = AddDealerForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.role = 'dealer'
            user.is_staff = True
            user.save()
            Group.objects.get_or_create(name='Dealers')[0].user_set.add(user)
            specialties = form.cleaned_data.get('job_specialty', [])
            other = form.cleaned_data.get('job_specialty_other','').strip()
            if 'Other' in specialties and other:
                specialties = [s for s in specialties if s!='Other'] + [other]
            Dealer.objects.create(
                user=user,
                name=f"{user.first_name} {user.last_name}",
                phone=user.phone,
                address=user.address,
                job_specialty=specialties
            )
            messages.success(request, "Dealer added.")
            return redirect('view_dealers')
    else:
        form = AddDealerForm()
    return render(request, 'main/add_dealer.html', {'form': form})

@login_required
def edit_dealer(request, dealer_id):
    if request.user.role != 'owner':
        return HttpResponseForbidden("You do not have permission to edit dealers.")
    dealer = get_object_or_404(Dealer, id=dealer_id)
    if request.method == 'POST':
        form = EditDealerForm(request.POST, instance=dealer)
        if form.is_valid():
            specialties = form.cleaned_data.get('job_specialty', [])
            other = form.cleaned_data.get('job_specialty_other','').strip()
            if 'Other' in specialties and other:
                specialties = [s for s in specialties if s!='Other'] + [other]
            dealer.job_specialty = specialties
            dealer.save()
            messages.success(request, "Dealer updated.")
            return redirect('view_dealers')
    else:
        form = EditDealerForm(instance=dealer)
    return render(request, 'main/edit_dealer.html', {'form': form, 'dealer': dealer})

@login_required
def delete_dealer(request, dealer_id):
    if request.user.role != 'owner':
        return HttpResponseForbidden("You do not have permission to delete dealers.")
    dealer = get_object_or_404(Dealer, id=dealer_id)
    if request.method == 'POST':
        if dealer.user:
            dealer.user.delete()
        messages.success(request, "Dealer deleted.")
        return redirect('view_dealers')
    return render(request, 'main/delete_dealer.html', {'dealer': dealer})

@login_required
def view_concierges(request):
    if request.user.role != 'owner':
        return HttpResponseForbidden("You do not have permission to view this page.")
    concierges = User.objects.filter(role='concierge')
    return render(request, 'main/view_concierges.html', {'concierges': concierges})

@login_required
def add_concierge(request):
    if request.user.role != 'owner':
        return HttpResponseForbidden("You do not have permission to add concierges.")
    if request.method == 'POST':
        form = AddConciergeForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.role = 'concierge'
            user.is_staff = False
            user.save()
            Group.objects.get_or_create(name='Concierge')[0].user_set.add(user)
            messages.success(request, "Concierge added.")
            return redirect('view_concierges')
    else:
        form = AddConciergeForm()
    return render(request, 'main/add_concierge.html', {'form': form})

@login_required
def edit_concierge(request, concierge_id):
    if request.user.role != 'owner':
        return HttpResponseForbidden("You do not have permission to edit concierges.")
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
def delete_concierge(request, concierge_id):
    if request.user.role != 'owner':
        return HttpResponseForbidden("You do not have permission to delete concierges.")
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
    if invoice_type == 1:
        invoice = get_object_or_404(Invoice1, id=invoice_id)
        if request.user != invoice.service_request.customer and request.user.role not in ['owner']:
            return HttpResponseForbidden("You do not have permission to view this invoice.")
    elif invoice_type == 2:
        invoice = get_object_or_404(Invoice2, id=invoice_id)
        if request.user.role not in ['owner', 'dealer']:
            return HttpResponseForbidden("You do not have permission to view this invoice.")
    else:
        raise Http404("Invalid invoice type.")
    return render(request, 'main/view_invoice.html', {
        'invoice': invoice,
        'invoice_type': invoice_type
    })

@login_required
def edit_invoice(request, invoice_id):
    if request.user.role != 'owner':
        return HttpResponseForbidden("You do not have permission to edit invoices.")
    invoice = (Invoice1.objects.filter(id=invoice_id).first()
               or Invoice2.objects.filter(id=invoice_id).first())
    if not invoice:
        messages.error(request, "Invoice not found.")
        return redirect("owner_dashboard")
    if request.method == "POST":
        old = invoice.payment_status
        invoice.price = request.POST.get("price", invoice.price)
        invoice.currency = request.POST.get("currency", invoice.currency)
        new = request.POST.get("payment_status", invoice.payment_status)
        invoice.payment_status = new
        invoice.updated_at = timezone.now()
        invoice.save()
        sr = invoice.service_request
        if sr and old != "Paid" and new == "Paid" and sr.status == "Waiting for Payment":
            sr.status = "Pending"
            sr.save()
        messages.success(request, "Invoice updated.")
        return redirect("owner_dashboard")
    else:
        form = (Invoice1Form(instance=invoice)
                if isinstance(invoice, Invoice1)
                else Invoice2Form(instance=invoice))
        return render(request, "main/edit_invoice.html", {
            "form": form,
            "invoice": invoice,
        })

# --------------------------
# Inventory
# --------------------------
@login_required
def view_inventory(request):
    if request.user.role != 'owner':
        return HttpResponseForbidden("You do not have permission to view this page.")
    items = Inventory.objects.all()
    return render(request, 'main/view_inventory.html', {'inventory': items})

@login_required
def add_inventory(request):
    if request.user.role != 'owner':
        return HttpResponseForbidden("You do not have permission to add inventory.")
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
def edit_inventory(request, inventory_id):
    if request.user.role != 'owner':
        return HttpResponseForbidden("You do not have permission to edit inventory.")
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
def delete_inventory(request, item_id):
    if request.user.role != 'owner':
        return JsonResponse({'status':'error','message':'No permission'}, status=403)
    try:
        item = Inventory.objects.get(id=item_id)
        if item.item_quantity > 1:
            item.item_quantity -= 1
            item.save()
            return JsonResponse({'status':'decremented','new_quantity':item.item_quantity})
        else:
            item.delete()
            return JsonResponse({'status':'deleted'})
    except Inventory.DoesNotExist:
        return JsonResponse({'status':'error','message':'Not found'}, status=404)

# --------------------------
# Real-time Location Updates
# --------------------------

@require_POST
@login_required
@user_passes_test(is_concierge)
def update_concierge_location(request, request_id):
    sr = get_object_or_404(
        ServiceRequest,
        id=request_id,
        assigned_to=request.user,
        status='Delivery'
    )
    if not sr.share_location:
        return HttpResponseForbidden("Location sharing is not enabled for this request.")
    try:
        data = json.loads(request.body)
        latitude = data.get('lat')
        longitude = data.get('lng')
        if latitude is not None and longitude is not None:
            sr.concierge_latitude = latitude
            sr.concierge_longitude = longitude
            sr.save(update_fields=['concierge_latitude', 'concierge_longitude'])
            return JsonResponse({'success': True})
        else:
            return JsonResponse({'success': False, 'error': 'Invalid location data.'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
def service_request_location(request, request_id):
    sr = get_object_or_404(ServiceRequest, id=request_id)
    if (
        request.user != sr.customer
        and request.user.role not in ['concierge','dealer','owner']
    ):
        return HttpResponseForbidden("No permission")
    if sr.share_location and sr.concierge_latitude is not None and sr.concierge_longitude is not None:
        return JsonResponse({
            'lat': sr.concierge_latitude,
            'lng': sr.concierge_longitude,
        })
    else:
        return JsonResponse({'error': 'Location not available'}, status=404)
