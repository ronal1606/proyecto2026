from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from django.core.mail import send_mail
from django.utils import timezone
from datetime import timedelta
from django.conf import settings
import random

# Vista principal - Login
def index(request):
    # Si el usuario ya está autenticado, redirigir al dashboard
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            # Generar OTP de 6 dígitos
            otp = str(random.randint(100000, 999999))
            
            # Asegurarse que el signal funcionó y tiene perfil
            if not hasattr(user, 'profile'):
                from app.models import UserProfile
                UserProfile.objects.create(user=user)
                
            user.profile.otp_code = otp
            user.profile.otp_created_at = timezone.now()
            user.profile.save()
            
            # Enviar correo HTML
            from django.template.loader import render_to_string
            from django.utils.html import strip_tags
            
            subject = '🔑 Tu código de verificación - BIGDATALAB'
            html_message = render_to_string('email_2fa.html', {
                'nombre': user.first_name or user.username,
                'otp_code': otp
            })
            plain_message = strip_tags(html_message)
            
            try:
                send_mail(
                    subject,
                    plain_message,
                    settings.DEFAULT_FROM_EMAIL,
                    [user.email],
                    html_message=html_message,
                    fail_silently=False,
                )
                messages.info(request, f'Se ha enviado un código de verificación a {user.email}')
            except Exception as e:
                messages.error(request, 'Aviso: No se pudo enviar el correo real (revisa tu consola de servidor o configura SMTP en .env).')
            
            # Guardamos la intención de login (sin autenticar la sesión permanentemente aún)
            request.session['pre_2fa_user_id'] = user.id
            return redirect('verify_2fa')
        else:
            messages.error(request, 'Usuario o contraseña incorrectos.')
    
    return render(request, 'index.html')


# Vista de registro
def register(request):
    # Si el usuario ya está autenticado, redirigir al dashboard
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')
        
        # Validaciones
        if password1 != password2:
            messages.error(request, 'Las contraseñas no coinciden.')
            return render(request, 'register.html')
        
        if len(password1) < 8:
            messages.error(request, 'La contraseña debe tener al menos 8 caracteres.')
            return render(request, 'register.html')
        
        if User.objects.filter(username=username).exists():
            messages.error(request, 'El nombre de usuario ya está en uso.')
            return render(request, 'register.html')
        
        if User.objects.filter(email=email).exists():
            messages.error(request, 'El correo electrónico ya está registrado.')
            return render(request, 'register.html')
        
        # Crear usuario
        try:
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password1,
                first_name=first_name,
                last_name=last_name
            )
            user.save()
            
            messages.success(request, '¡Cuenta creada exitosamente! Por favor inicia sesión.')
            return redirect('index')
        
        except Exception as e:
            messages.error(request, f'Error al crear la cuenta: {str(e)}')
    
    return render(request, 'register.html')


# Vista del dashboard (requiere autenticación)
@login_required(login_url='index')
def dashboard(request):
    return render(request, 'dashboard.html')


# Vista de logout
@login_required(login_url='index')
def logout_view(request):
    auth_logout(request)
    messages.success(request, 'Has cerrado sesión correctamente.')
    return redirect('index')

# Vista de Nosotros (Plataforma ML BIGDATALAB)
@login_required(login_url='index')
def nosotros(request):
    return render(request, 'nosotros.html')

# Vista de Verificación 2FA
def verify_2fa(request):
    user_id = request.session.get('pre_2fa_user_id')
    if not user_id:
        return redirect('index')
    
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return redirect('index')
        
    if request.method == 'POST':
        entered_code = request.POST.get('otp_code')
        
        if not hasattr(user, 'profile') or not user.profile.otp_code or not user.profile.otp_created_at:
            messages.error(request, 'No hay código pendiente de verificación.')
            return redirect('index')
            
        # Verificar expiración (5 mins)
        if timezone.now() > user.profile.otp_created_at + timedelta(minutes=5):
            messages.error(request, 'El código de verificación ha expirado. Por favor, inicia sesión de nuevo.')
            user.profile.otp_code = None
            user.profile.save()
            try:
                del request.session['pre_2fa_user_id']
            except KeyError:
                pass
            return redirect('index')
            
        if entered_code == user.profile.otp_code:
            # Limpiar estado 2FA
            user.profile.otp_code = None
            user.profile.save()
            try:
                del request.session['pre_2fa_user_id']
            except KeyError:
                pass
            
            # Autenticar usuario permanentemente (Login exitoso)
            auth_login(request, user)
            messages.success(request, f'¡Bienvenido de vuelta, {user.first_name or user.username}!', extra_tags='success')
            return redirect('dashboard')
        else:
            messages.error(request, 'El código de verificación es incorrecto.')
            
    # Enmascarar el correo (ej. ronal***@gmail.com -> r***l@gmail.com no, mejor: r****l@gmail.com)
    email = user.email
    if '@' in email:
        username_part, domain_part = email.split('@')
        if len(username_part) > 2:
            obfuscated_email = f"{username_part[0]}{'*' * (len(username_part)-2)}{username_part[-1]}@{domain_part}"
        else:
            obfuscated_email = f"{username_part[0]}***@{domain_part}"
    else:
        obfuscated_email = "***"
            
    return render(request, 'verify_2fa.html', {'email': obfuscated_email})
