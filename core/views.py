import json
import logging
import os
import tempfile
from http.cookiejar import logger

import imgkit
from PIL import Image
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.files.base import ContentFile
from django.db import transaction
from django.http import HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
import requests
from django.views.decorators.http import require_POST, require_GET
from weasyprint import HTML
from weasyprint.text.fonts import FontConfiguration

from carehome_project import settings
from core.utils import get_or_create_latest_log, get_filtered_queryset, generate_shift_times
from .models import CustomUser, LatestLogEntry, Mapping
from .forms import ServiceUserForm, StaffCreationForm, CareHomeForm, MappingForm
from io import BytesIO
from django.template.loader import render_to_string
from django.http import HttpResponse
from xhtml2pdf import pisa
from .models import ABCForm, IncidentReport
from .forms import ABCFormForm, IncidentReportForm
from django.contrib import messages
from datetime import datetime, timedelta
from django.utils import timezone
from django.shortcuts import render, redirect, get_object_or_404
from .models import CareHome, ServiceUser, LogEntry
from .forms import LogEntryForm
from django.http import JsonResponse
from datetime import time


def get_shifts_from_carehome(carehome):
    from datetime import datetime, timedelta, date

    if not carehome or not carehome.day_shift_start:
        return []

    start = carehome.day_shift_start
    day_end = (datetime.combine(date.today(), start) + timedelta(hours=12)).time()
    night_end = (datetime.combine(date.today(), start) + timedelta(hours=24)).time()

    return [
        f"Day Shift ({start.strftime('%I:%M %p')} - {day_end.strftime('%I:%M %p')})",
        f"Night Shift ({day_end.strftime('%I:%M %p')} - {night_end.strftime('%I:%M %p')})"
    ]


def create_log_view(request):
    carehomes = CareHome.objects.all()
    selected_carehome_id = request.GET.get('carehome') or request.POST.get('carehome')
    service_users = []
    shifts = []

    selected_carehome = None
    if selected_carehome_id:
        try:
            selected_carehome = CareHome.objects.get(id=selected_carehome_id)
            service_users = ServiceUser.objects.filter(carehome=selected_carehome)
            shifts = get_shifts_from_carehome(selected_carehome)
        except CareHome.DoesNotExist:
            messages.error(request, "Selected carehome does not exist.")

    if request.method == 'POST' and 'start_log' in request.POST:
        carehome_id = request.POST.get('carehome')
        shift = request.POST.get('shift')
        service_user_id = request.POST.get('service_user')

        if not all([carehome_id, shift, service_user_id]):
            messages.error(request, "All fields are required.")
        else:
            request.session['log_info'] = {
                'carehome_id': carehome_id,
                'shift': shift,
                'service_user_id': service_user_id
            }
            return redirect('log-entry-form')

    return render(request, 'pdf_templates/select_log_data.html', {
        'carehomes': carehomes,
        'service_users': service_users,
        'shifts': shifts,
        'selected_carehome_id': selected_carehome_id,
    })


def render_pdf_view(template_src, context_dict):
    html = render_to_string(template_src, context_dict)
    result = BytesIO()
    pdf = pisa.pisaDocument(BytesIO(html.encode("UTF-8")), result)
    if not pdf.err:
        return HttpResponse(result.getvalue(), content_type='application/pdf')
    return HttpResponse('Error generating PDF', status=500)


logger = logging.getLogger(__name__)


@login_required
def fill_abc_form(request):
    if request.method == 'POST':
        form = ABCFormForm(request.POST)
        if form.is_valid():
            try:
                instance = form.save(commit=False)
                instance.created_by = request.user

                # Combine individual fields
                instance.setting = "\n".join([
                    f"Location: {request.POST.get('setting_location', '')}",
                    f"Present: {request.POST.get('setting_present', '')}",
                    f"Activity: {request.POST.get('setting_activity', '')}",
                    f"Environment: {request.POST.get('setting_environment', '')}"
                ])

                instance.antecedent = "\n".join([
                    f"Description: {request.POST.get('antecedent_description', '')}",
                    f"Routine change: {request.POST.get('antecedent_change', '')}",
                    f"Unexpected noise: {request.POST.get('antecedent_noise', '')}",
                    f"Waiting for: {request.POST.get('antecedent_waiting', '')}"
                ])

                instance.behaviour = "\n".join([
                    f"Description: {request.POST.get('behaviour_description', '')}",
                    f"Duration: {request.POST.get('behaviour_duration', '')}",
                    f"Intensity: {request.POST.get('behaviour_intensity', '')}"
                ])

                instance.consequences = "\n".join([
                    f"Immediate: {request.POST.get('consequence_immediate', '')}",
                    f"Staff response: {request.POST.get('consequence_staff', '')}",
                    f"Others reacted: {request.POST.get('consequence_others', '')}"
                ])

                instance.reflection = "\n".join([
                    f"Learnings: {request.POST.get('reflection_learnings', '')}",
                    f"Strategies: {request.POST.get('reflection_strategies', '')}",
                    f"Notes: {request.POST.get('reflection_notes', '')}"
                ])

                instance.save()
                form.save_m2m()

                # PDF Generation - Using BytesIO (recommended approach)
                context = {
                    'data': {
                        'target_behaviours': form.cleaned_data['target_behaviours'],
                        'service_user': instance.service_user,
                        'date_of_birth': instance.date_of_birth,
                        'staff': instance.staff,
                        'date_time': instance.date_time,
                        'setting': instance.setting,
                        'antecedent': instance.antecedent,
                        'behaviour': instance.behaviour,
                        'consequences': instance.consequences,
                        'reflection': instance.reflection
                    }
                }

                html_string = render_to_string('pdf_templates/abc_pdf.html', context)
                pdf_bytes = HTML(string=html_string).write_pdf()
                file_content = ContentFile(pdf_bytes)
                filename = f'abc_form_{instance.id}_{instance.date_time.date()}.pdf'
                instance.pdf_file.save(filename, file_content, save=True)
                messages.success(request, 'ABC Form saved successfully!')
                return redirect('abc_form_list')

            except Exception as e:
                messages.error(request, f'Error saving form: {str(e)}')
                logger.exception("Error saving ABC form")
        else:
            messages.error(request, 'Please correct the form errors')
            logger.debug(f"Form errors: {form.errors}")
    else:
        form = ABCFormForm(initial={'staff': request.user.get_full_name()})

    return render(request, 'forms/abc_form.html', {'form': form})


@login_required
def abc_form_list(request):
    """Show list of forms with visibility control"""
    if request.user.is_superuser:
        forms = ABCForm.objects.all().order_by('-date_time')
    elif request.user.groups.filter(name='Supervisors').exists():
        forms = ABCForm.objects.filter(
            service_user__in=request.user.managed_clients.all()
        ).order_by('-date_time')
    else:  # Regular care staff
        forms = ABCForm.objects.filter(
            created_by=request.user
        ).order_by('-date_time')

    return render(request, 'forms/abc_form_list.html', {'forms': forms})


@login_required
def view_abc_form(request, form_id):
    """View form with permission check"""
    instance = get_object_or_404(ABCForm, id=form_id)

    # Permission check
    if not (request.user.is_superuser or
            request.user == instance.created_by or
            request.user.groups.filter(name='Supervisors').exists() and
            instance.service_user in request.user.managed_clients.all()):
        return HttpResponse("Not authorized", status=403)

    return render(request, 'view_abc_form.html', {'form': instance})


@login_required
def download_abc_pdf(request, form_id):
    """Download PDF with permission check"""
    instance = get_object_or_404(ABCForm, id=form_id)

    # Permission check
    if not (request.user.is_superuser or
            request.user == instance.created_by or
            request.user.groups.filter(name='Supervisors').exists() and
            instance.service_user in request.user.managed_clients.all()):
        return HttpResponse("Not authorized", status=403)

    if not instance.pdf_file:
        return HttpResponse("PDF not available", status=404)

    response = HttpResponse(instance.pdf_file, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="abc_form_{instance.id}.pdf"'
    return response


@login_required
def edit_abc_form(request, form_id):
    instance = get_object_or_404(ABCForm, id=form_id)
    if request.method == 'POST':
        form = ABCFormForm(request.POST, instance=instance)
        if form.is_valid():
            updated = form.save()

            # Regenerate PDF
            html_string = render_to_string('pdf_templates/abc_pdf.html', {'data': updated})
            with tempfile.NamedTemporaryFile(delete=True, suffix='.pdf') as output:
                HTML(string=html_string).write_pdf(output.name)
                with open(output.name, 'rb') as pdf_file:
                    file_content = ContentFile(pdf_file.read())
                    filename = f'abc_form_{updated.id}.pdf'
                    updated.pdf_file.save(filename, file_content, save=True)

            return redirect('abc_form_list')
    else:
        form = ABCFormForm(instance=instance)
    return render(request, 'forms/abc_form.html', {'form': form, 'edit': True})


@login_required
def fill_incident_form(request):
    if request.method == 'POST':
        form = IncidentReportForm(request.POST)
        if form.is_valid():
            instance = form.save(commit=False)
            instance.staff = request.user
            instance.carehome = form.cleaned_data['service_user'].carehome  # auto-link carehome
            instance.save()

            # Generate HTML for PDF
            html_string = render_to_string('pdf_templates/incident_pdf.html', {'data': instance})

            # Generate PDF using WeasyPrint
            temp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
            temp_pdf.close()  # Close so WeasyPrint can write to it

            HTML(string=html_string).write_pdf(temp_pdf.name)

            with open(temp_pdf.name, 'rb') as pdf_file:
                file_content = ContentFile(pdf_file.read())
                filename = f'incident_report_{instance.id}.pdf'
                instance.pdf_file.save(filename, file_content)

            os.unlink(temp_pdf.name)
            return redirect('incident_report_list')
    else:
        form = IncidentReportForm()

    return render(request, 'forms/incident_form.html', {'form': form})


def download_incident_pdf(request, form_id):
    form_data = get_object_or_404(IncidentReport, id=form_id)

    # Render the template as string
    html_string = render_to_string('pdf_templates/incident_pdf.html', {'data': form_data})

    # Generate PDF from HTML string
    pdf_file = HTML(string=html_string).write_pdf()

    # Return PDF as downloadable response
    response = HttpResponse(pdf_file, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="incident_report_{form_id}.pdf"'
    return response


User = get_user_model()


def login_view(request):
    print("Login view accessed")
    if request.method == 'POST':
        print("POST data:", request.POST)
        email = request.POST.get('username')  # Now we only use email
        password = request.POST.get('password')
        print(f"Attempting auth for {email}")

        user = authenticate(request, email=email, password=password)
        print("User object:", user)

        if user is not None:
            login(request, user)
            print("Login successful, redirecting...")

            # Update last active time
            user.last_active = timezone.now()
            user.save()

            if user.is_superuser:
                return redirect('admin-dashboard')
            elif user.role == CustomUser.STAFF:
                return redirect('admin-dashboard')
            else:
                return redirect('staff-dashboard')
        else:
            print("Authentication failed")
            return render(request, 'core/login.html', {
                'error': 'Invalid email or password'
            })

    return render(request, 'core/login.html')


@login_required
def dashboard(request):
    user = request.user

    if user.is_superuser or user.role == CustomUser.Manager:
        context = {
            "active_users_count": CustomUser.objects.filter(is_active=True).count(),
            "incident_reports_count": IncidentReport.objects.count(),
            "abc_forms_count": ABCForm.objects.count(),
            "latest_logs_count": LatestLogEntry.objects.count(),
            "missed_logs_count": LogEntry.objects.filter(is_locked=False, content="",
                                                         date__lt=timezone.localdate()).count(),
            "recent_carehomes": CareHome.objects.order_by("-created_at")[:5],
            "can_add_carehome": True,  # Show 'Add New Carehome' button
        }
        return render(request, "core/dashboard.html", context)

    elif user.role == CustomUser.TEAM_LEAD:
        carehome = user.carehome
        staff_users = CustomUser.objects.filter(role='staff', carehome=carehome)
        latest_logs_qs = LatestLogEntry.objects.filter(user__in=staff_users)

        context = {
            "active_users_count": staff_users.filter(is_active=True).count(),
            "incident_reports_count": IncidentReport.objects.filter(carehome=carehome).count(),
            "abc_forms_count": ABCForm.objects.filter(service_user__carehome=carehome).count(),
            "latest_logs_count": latest_logs_qs.count(),
            "missed_logs_count": LogEntry.objects.filter(
                user__in=staff_users,
                is_locked=False,
                content="",
                date__lt=timezone.localdate()
            ).count(),
            "recent_carehomes": CareHome.objects.filter(id=carehome.id),
            "can_add_carehome": False,
        }
        return render(request, "core/dashboard.html", context)


    elif user.role == CustomUser.STAFF:
        context = {
            "incident_reports_count": IncidentReport.objects.filter(staff=user).count(),
            "abc_forms_count": ABCForm.objects.filter(created_by=user).count(),
            "latest_logs_count": LatestLogEntry.objects.filter(user=user).count(),
            "missed_logs_count": LogEntry.objects.filter(user=user, is_locked=False, content="",
                                                         date__lt=timezone.localdate()).count(),
        }
        return render(request, "core/staff_dashboard.html", context)

    return redirect("login")


def logout_view(request):
    logout(request)
    return redirect('login')


@login_required
def create_staff(request):
    carehomes = CareHome.objects.all()

    if request.method == 'POST':
        form = StaffCreationForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                staff = form.save(commit=False)

                if 'image' in request.FILES:
                    print(f"\nUploading file: {request.FILES['image'].name}")
                    staff.image = request.FILES['image']

                if staff.role == CustomUser.TEAM_LEAD:
                    staff.is_staff = True

                staff.save()
                messages.success(request, 'Staff member created successfully!')
                return redirect('staff-dashboard')

            except Exception as e:
                messages.error(request, f'Error saving staff: {str(e)}')
                logger.error(f"Staff creation error: {str(e)}")
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")

    form = form if request.method == 'POST' else StaffCreationForm()
    return render(request, 'staff/create.html', {
        'form': form,
        'carehomes': carehomes,
        'edit_mode': False
    })


@login_required
def edit_staff(request, pk):
    staff = get_object_or_404(CustomUser, pk=pk)
    carehomes = CareHome.objects.all()

    if request.method == 'POST':
        form = StaffCreationForm(request.POST, request.FILES, instance=staff)
        if form.is_valid():
            staff = form.save(commit=False)
            if staff.role == CustomUser.TEAM_LEAD:
                staff.is_staff = True
            else:
                staff.is_staff = False
            staff.save()
            return redirect('staff-dashboard')
    else:
        form = StaffCreationForm(instance=staff)

    return render(request, 'staff/create.html', {
        'form': form,
        'carehomes': carehomes,
        'edit_mode': True
    })


@login_required
def toggle_staff_status(request, pk):
    staff = get_object_or_404(CustomUser, pk=pk)
    staff.is_active = not staff.is_active
    staff.save()
    return redirect('staff-dashboard')


@login_required
def staff_dashboard(request):
    if request.user.role == CustomUser.TEAM_LEAD:
        staff_list = CustomUser.objects.filter(carehome=request.user.carehome)
    elif request.user.is_superuser:
        staff_list = CustomUser.objects.all()
    else:
        staff_list = CustomUser.objects.filter(pk=request.user.pk)

    return render(request, 'staff/dashboard.html', {'staff_list': staff_list})


# The rest of your views (carehomes, service users) remain the same
def carehomes_dashboard(request):
    carehomes = CareHome.objects.all().order_by('-created_at')
    return render(request, 'carehomes/dashboard.html', {'carehomes': carehomes})


def create_carehome(request):
    if request.method == 'POST':
        form = CareHomeForm(request.POST, request.FILES)
        if form.is_valid():
            postcode = form.cleaned_data['postcode'].replace(' ', '')
            api_valid = validate_postcode_with_api(postcode)

            if api_valid:
                carehome = form.save()
                messages.success(request, f'Carehome "{carehome.name}" created successfully!')
                return redirect('carehomes-dashboard')
            else:
                messages.error(request, 'Invalid postcode - please enter a valid UK postcode')
        else:
            messages.error(request, 'Please correct the errors below')
    else:
        form = CareHomeForm()

    return render(request, 'carehomes/create.html', {'form': form})

def edit_carehome(request, id):
    carehome = get_object_or_404(CareHome, id=id)
    if request.method == 'POST':
        form = CareHomeForm(request.POST, request.FILES, instance=carehome)
        if form.is_valid():
            form.save()
            return redirect('carehomes-dashboard')
    else:
        form = CareHomeForm(instance=carehome)
    return render(request, 'carehomes/create.html', {'form': form, 'edit_mode': True})

def delete_carehome(request, id):
    carehome = get_object_or_404(CareHome, id=id)
    carehome.delete()
    return redirect('carehomes-dashboard')


def validate_postcode_with_api(postcode):
    try:
        response = requests.get(f'https://api.postcodes.io/postcodes/{postcode}/validate')
        if response.status_code == 200:
            data = response.json()
            return data.get('result', False)
        return False
    except requests.RequestException:
        return False


def create_service_user(request):
    carehomes = CareHome.objects.all()
    if request.method == 'POST':
        form = ServiceUserForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('service-users-dashboard')
    else:
        form = ServiceUserForm()

    return render(request, 'service_users/create.html', {
        'form': form,
        'carehomes': carehomes
    })


def edit_service_user(request, id):
    service_user = get_object_or_404(ServiceUser, id=id)
    carehomes = CareHome.objects.all()

    if request.method == 'POST':
        form = ServiceUserForm(request.POST, request.FILES, instance=service_user)
        if form.is_valid():
            form.save()
            return redirect('service-users-dashboard')
    else:
        form = ServiceUserForm(instance=service_user)

    return render(request, 'service_users/create.html', {
        'form': form,
        'edit_mode': True,
        'carehomes': carehomes
    })


def delete_service_user(request, id):
    service_user = get_object_or_404(ServiceUser, id=id)
    service_user.delete()
    return redirect('service-users-dashboard')


def service_users_dashboard(request):
    service_users = ServiceUser.objects.all().order_by('-created_at')
    return render(request, 'service_users/dashboard.html', {'service_users': service_users})


@csrf_exempt
def validate_postcode(request):
    if request.method == 'POST':
        postcode = request.POST.get('postcode', '').replace(' ', '')
        try:
            response = requests.get(f'https://api.postcodes.io/postcodes/{postcode}/validate')
            if response.status_code == 200:
                data = response.json()
                return JsonResponse({'valid': data.get('result', False)})
            return JsonResponse({'valid': False})
        except requests.RequestException:
            return JsonResponse({'valid': False})
    return JsonResponse({'valid': False})


@login_required
def active_users_view(request):
    staff_list = get_filtered_queryset(CustomUser, request.user)
    return render(request, 'core/active_users.html', {'staff_list': staff_list})


@login_required
def missed_logs_view(request):
    logs = get_filtered_queryset(LogEntry, request.user).filter(
        is_locked=False,
        content="",
        date__lt=timezone.localdate()
    )
    return render(request, 'core/missed_logs.html', {'missed_logs': logs})


def coerce_to_time(val):
    if isinstance(val, datetime.time):
        return val
    if isinstance(val, str):
        h, m = map(int, val.split(":"))
        return datetime.time(h, m)
    return None


@login_required
def view_latest_log_detail(request, pk):
    log = get_object_or_404(LatestLogEntry, id=pk)

    if request.user.role not in ['team_lead'] and not request.user.is_superuser:
        return HttpResponseForbidden("You are not allowed to view this log.")

    if log.log_pdf:
        # render PDF into HTML form OR show download
        return render(request, 'forms/log_entry_from_pdf.html', {'log': log})
    else:
        # fallback to show log data
        return redirect('log-entry-form')


@login_required
def staff_latest_logs_view(request):
    user = request.user

    if user.is_superuser:
        # Manager view: show all staff logs sorted by latest
        logs = LatestLogEntry.objects.all().order_by('-date', '-created_at')

    elif user.role == 'team_lead':
        # Team Lead view: show logs of staff in same carehome
        staff_users = CustomUser.objects.filter(role='staff', carehome=user.carehome)
        logs = LatestLogEntry.objects.filter(user__in=staff_users).order_by('-date', '-created_at')

    else:
        # Staff: only own logs
        logs = LatestLogEntry.objects.filter(user=user).order_by('-date', '-created_at')

    return render(request, 'forms/staff_latest_logs.html', {'logs': logs})


@csrf_exempt
def fetch_service_users(request):
    if request.method == "POST":
        data = json.loads(request.body)
        carehome_ids = data.get('carehome_ids', [])
        users = ServiceUser.objects.filter(carehome_id__in=carehome_ids)

        response = {
            'users': [{'id': su.id, 'name': str(su)} for su in users]
        }
        return JsonResponse(response)
    return JsonResponse({'error': 'Invalid method'}, status=400)


def staff_mapping_view(request):
    mappings = Mapping.objects.all()
    form = MappingForm()

    if request.method == "POST":
        form = MappingForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('staff-mapping')  # replace with your URL name

    context = {
        'form': form,
        'mappings': mappings,
        'show_form': request.method == "POST" or 'show_form' in request.GET
    }
    return render(request, 'core/staff_mapping.html', context)


def create_mapping(request):
    if request.method == 'POST':
        form = MappingForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('mapping_success')  # or your desired success route
    else:
        form = MappingForm()
    return render(request, 'core/staff_mapping.html', {'form': form})


def load_service_users(request):
    carehome_ids = request.GET.getlist('carehome_ids[]')
    users = ServiceUser.objects.filter(carehome_id__in=carehome_ids)
    data = [{'id': u.id, 'name': f"{u.first_name} {u.last_name}"} for u in users]
    return JsonResponse({'service_users': data})


@login_required
def log_detail_view(request, pk):
    latest_log = get_object_or_404(LatestLogEntry, pk=pk)
    user = request.user

    # Permission logic
    is_owner = latest_log.user == user
    is_superuser = user.is_superuser
    is_manager = user.role == 'manager'
    is_team_lead = user.role == 'team_lead'

    # Determine access rights
    can_view = False
    can_edit = False

    if is_superuser or is_manager:
        # Managers/superusers can view/edit all logs
        can_view = True
        can_edit = not latest_log.status == 'locked'

    elif is_team_lead:
        # Team leads can view/edit logs from their carehome
        if latest_log.carehome == user.carehome:
            can_view = True
            can_edit = (is_owner or not latest_log.status == 'locked')

    elif is_owner:
        # Owners can always view their own logs
        can_view = True
        can_edit = not latest_log.status == 'locked'

    else:
        # Regular staff can only view if they're assigned to the same carehome
        if hasattr(user, 'carehome') and latest_log.carehome == user.carehome:
            can_view = True

    if not can_view:
        return HttpResponseForbidden("You don't have permission to view this log")

    # Get log entries
    log_entries = LogEntry.objects.filter(
        service_user=latest_log.service_user,
        date=latest_log.date,
        shift=latest_log.shift
    ) 

    context = {
        'latest_log': latest_log,
        'log_entries': log_entries,
        'can_edit': can_edit,
        'user_role': user.role
    }

    return render(request, 'logs/log_detail.html', context)


@login_required
def incident_report_list_view(request):
    user = request.user

    if user.is_superuser or user.role == 'manager':
        # Managers see all incidents
        incidents = IncidentReport.objects.select_related('service_user').order_by('-incident_datetime')

    elif user.role == 'team_lead':
        # Team leads see incidents in their carehome
        incidents = IncidentReport.objects.filter(service_user__carehome=user.carehome).order_by('-incident_datetime')

    elif user.role == 'staff':
        # Staff see only incidents they submitted
        incidents = IncidentReport.objects.filter(staff=user).order_by('-incident_datetime')

    else:
        # Other roles see nothing or can be handled separately
        incidents = IncidentReport.objects.none()

    return render(request, 'forms/incident_report_list.html', {'incidents': incidents})


@login_required
def edit_incident_form(request, form_id):
    instance = get_object_or_404(IncidentReport, id=form_id)

    if request.method == 'POST':
        form = IncidentReportForm(request.POST, instance=instance)
        if form.is_valid():
            instance = form.save(commit=False)
            instance.staff = request.user
            instance.carehome = form.cleaned_data['service_user'].carehome
            instance.save()

            # Regenerate PDF
            html_string = render_to_string('pdf_templates/incident_pdf.html', {'data': instance})
            with tempfile.NamedTemporaryFile(delete=True, suffix='.pdf') as output:
                HTML(string=html_string).write_pdf(output.name)
                with open(output.name, 'rb') as pdf_file:
                    file_content = ContentFile(pdf_file.read())
                    filename = f'incident_report_{instance.id}.pdf'
                    instance.pdf_file.save(filename, file_content)

            return redirect('incident_detail', form_id=instance.id)
    else:
        form = IncidentReportForm(instance=instance)

    return render(request, 'forms/incident_form.html', {'form': form})


@login_required
def create_log_view(request):
    mapping = Mapping.objects.filter(staff=request.user).first()
    if not mapping:
        return render(request, 'error.html', {'message': 'No mappings found for your account.'})

    if request.method == "POST":
        carehome = get_object_or_404(CareHome, id=request.POST.get("carehome"))
        service_user = get_object_or_404(ServiceUser, id=request.POST.get("service_user"))
        shift = request.POST.get("shift")
        today = timezone.localdate()

        latest_log, created = LatestLogEntry.objects.get_or_create(
            user=request.user,
            carehome=carehome,
            service_user=service_user,
            shift=shift,
            date=today,
            defaults={'status': 'incomplete'}
        )

        return redirect('log-entry-form', latest_log_id=latest_log.id)

    return render(request, 'logs/log_entry_create.html', {
        "carehomes": mapping.carehomes.all(),
        "service_users": mapping.service_users.all(),
        "shifts": ['Morning', 'Night']  # ✅ FINAL SHIFT OPTIONS
    })


def view_incident_report(request, pk):
    # Get the incident report or return 404 if not found
    incident = get_object_or_404(IncidentReport, pk=pk)

    # Prepare the context data to pass to the template
    context = {
        'data': {
            'incident_datetime': incident.incident_datetime,
            'location': incident.location,
            'service_user': incident.service_user,
            'dob': incident.dob,  # Assuming service_user is a ForeignKey
            'staff_involved': incident.staff_involved,
            'prior_description': incident.prior_description,
            'incident_description': incident.incident_description,
            'user_response': incident.user_response,
            'injuries_detail': incident.injuries_detail,
            'prn_administered': incident.prn_administered,
            'prn_by_whom': incident.prn_by_whom,
            'contacted_manager': incident.contacted_manager,
            'contacted_police': incident.contacted_police,
            'contacted_paramedics': incident.contacted_paramedics,
            # Add any other fields you need
        }
    }

    return render(request, 'core\incident_report_template.html', context)


def generate_log_pdf(latest_log):
    try:
        # Get all entries for this log, including those that might not have latest_log set
        log_entries = LogEntry.objects.filter(
            user=latest_log.user,
            carehome=latest_log.carehome,
            service_user=latest_log.service_user,
            date=latest_log.date,
            shift=latest_log.shift
        ) 

        # Also update these entries to point to the latest_log
        log_entries.update(latest_log=latest_log)

        html_string = render_to_string('pdf_templates/log_pdf.html', {
            'latest_log': latest_log,
            'log_entries': log_entries,
        })

        # Ensure directory exists
        os.makedirs(os.path.join(settings.MEDIA_ROOT, 'log_pdfs'), exist_ok=True)

        pdf_filename = f"log_{latest_log.id}.pdf"
        pdf_path = os.path.join(settings.MEDIA_ROOT, 'log_pdfs', pdf_filename)

        HTML(string=html_string).write_pdf(pdf_path)

        latest_log.log_pdf.name = f'log_pdfs/{pdf_filename}'
        latest_log.save()
        return True
    except Exception as e:
        print(f"Error generating PDF: {str(e)}")
        return False


@login_required
def log_entry_form(request, latest_log_id):
    latest_log = get_object_or_404(LatestLogEntry, id=latest_log_id)
    shift = latest_log.shift.lower()
    carehome = latest_log.carehome
    service_user = latest_log.service_user
    today = latest_log.date

    # Dynamically choose shift start time
    if shift == "morning":
        base_start_time = carehome.morning_shift_start or time(8, 0)
    elif shift == "night":
        base_start_time = carehome.night_shift_start or time(20, 0)
    else:
        base_start_time = time(8, 0)  # fallback

    time_slots = generate_shift_times(base_start_time)

    log_entries = []
    for slot in time_slots:
        entry, _ = LogEntry.objects.get_or_create(
            user=latest_log.user,
            carehome=latest_log.carehome,
            service_user=latest_log.service_user,
            shift=latest_log.shift,
            date=latest_log.date,
            time_slot=slot
        )
        log_entries.append(entry)

    return render(request, 'forms/log_entry_form.html', {
        'log_entries': log_entries,
        'latest_log': latest_log,
        'shift': latest_log.shift,  # Add this
        'carehome': carehome,  # Add this
        'service_user': service_user,  # Add this
        'today': today  # Add this
    })


@login_required
def lock_log_entries(request, latest_log_id):
    try:
        # Get the log entry with proper permission checking
        latest_log = get_object_or_404(
            LatestLogEntry,
            id=latest_log_id,
            user=request.user  # Ensures user owns this log
        )

        # Start atomic transaction
        with transaction.atomic():
            # Lock all related entries
            updated = LogEntry.objects.filter(
                latest_log=latest_log,
                is_locked=False  # Only lock unlocked entries
            ).update(is_locked=True)

            # Update log status
            latest_log.status = 'locked'
            latest_log.save()

            # Generate PDF
            if not generate_log_pdf(latest_log):
                raise Exception("PDF generation failed")

            messages.success(request, f"Successfully locked log with {updated} entries")
            return redirect('staff-dashboard')

    except Exception as e:
        messages.error(request, f"Error locking log: {str(e)}")
        return redirect('staff-dashboard')


@login_required
def edit_log_entry_by_admin(request, latest_log_id):
    log = get_object_or_404(LatestLogEntry, id=latest_log_id)

    if request.user.role not in ['team_lead', 'manager'] and not request.user.is_superuser:
        return HttpResponseForbidden("Permission denied.")

    entries = LogEntry.objects.filter(latest_log=log)
    return render(request, 'forms/log_entry_form.html', {
        'log_entries': entries,
        'latest_log': log,
        'admin_edit': True
    })


@require_POST
@login_required
def save_log_entry(request, entry_id):
    entry = get_object_or_404(LogEntry, id=entry_id)
    content = request.POST.get('content', '').strip()

    if not content:
        return JsonResponse({'success': False, 'error': 'Content cannot be empty'})

    try:
        with transaction.atomic():
            # REMOVED THE is_locked CHECK
            entry.content = content
            entry.save()

            if entry.latest_log:
                entry.latest_log.status = 'incomplete'
                entry.latest_log.save()
                if hasattr(entry.latest_log, 'generate_pdf'):
                    entry.latest_log.generate_pdf()

        return JsonResponse({'success': True})

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


def get_staff_by_carehome(request):
    carehome_id = request.GET.get('carehome_id')
    staff = User.objects.filter(carehome_id=carehome_id).values('id', 'first_name', 'last_name')
    staff_list = [{
        'id': s['id'],
        'name': f"{s['first_name']} {s['last_name']}"
    } for s in staff]
    return JsonResponse({'staff': staff_list})


@require_GET
def get_service_users_by_carehome(request):
    # Get the raw parameter value
    carehome_param = request.GET.get('carehome_id') or request.GET.get('carehome_id[]')

    if not carehome_param:
        return JsonResponse({'service_users': []}, status=400)

    try:
        # Handle both single ID and comma-separated IDs
        if ',' in carehome_param:
            carehome_ids = [int(id.strip()) for id in carehome_param.split(',')]
            service_users = ServiceUser.objects.filter(carehome_id__in=carehome_ids)
        else:
            service_users = ServiceUser.objects.filter(carehome_id=int(carehome_param))

        users_list = [{
            'id': user.id,
            'name': user.get_formatted_name()
        } for user in service_users]

        return JsonResponse({'service_users': users_list})

    except (ValueError, TypeError) as e:
        return JsonResponse({'error': 'Invalid carehome ID format'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)