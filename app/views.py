from django.shortcuts import render, redirect, get_object_or_404
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
    from app.models import ModeloML
    # Contamos estadisticas básicas de los modelos en BD
    modelos_activos = ModeloML.objects.filter(estado='activo').count()
    experimentos_doc = ModeloML.objects.exclude(documento_estudio='').count()
    # "Ejecuciones totales" por ahora pondremos una estimación basada en modelos o un conteo general si tuvieramos tabla. Como no hay, enviamos un placeholder o sumatoria
    ejecuciones_totales = ModeloML.objects.count() * 12 # Simulación de uso o puedes dejar "0" si prefieres
    
    context = {
        'modelos_activos': modelos_activos,
        'experimentos_doc': experimentos_doc,
        'ejecuciones_totales': ejecuciones_totales,
    }
    return render(request, 'dashboard.html', context)


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


# ====================================================
# MÓDULO DE CATÁLOGO DE MODELOS ML
# ====================================================

@login_required(login_url='index')
def modelos_lista(request):
    from app.models import ModeloML
    
    query = request.GET.get('q', '')
    categoria = request.GET.get('categoria', '')

    modelos = ModeloML.objects.all().order_by('-fecha_creacion')
    
    if query:
        modelos = modelos.filter(nombre__icontains=query) | modelos.filter(nombre_estudio__icontains=query) | modelos.filter(descripcion__icontains=query)
    if categoria:
        modelos = modelos.filter(categoria=categoria)

    CATEGORIAS = ModeloML.CATEGORIA_CHOICES
    
    return render(request, 'modelos_lista.html', {
        'modelos': modelos,
        'categorias': CATEGORIAS,
        'query': query,
        'categoria_activa': categoria,
    })


@login_required(login_url='index')
def modelo_crear(request):
    from app.models import ModeloML
    
    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        nombre_estudio = request.POST.get('nombre_estudio')
        descripcion = request.POST.get('descripcion')
        categoria = request.POST.get('categoria')
        estado = request.POST.get('estado', 'activo')
        precision = request.POST.get('precision') or None
        archivo_modelo = request.FILES.get('archivo_modelo')
        documento_estudio = request.FILES.get('documento_estudio')
        
        # Nuevos metadatos
        img_width = request.POST.get('img_width', 28)
        img_height = request.POST.get('img_height', 28)
        es_rgb = request.POST.get('es_rgb') == 'on'
        invertir_colores = request.POST.get('invertir_colores') == 'on'
        nombres_clases = request.POST.get('nombres_clases', '')
        
        if not nombre or not nombre_estudio or not descripcion or not categoria or not archivo_modelo:
            messages.error(request, 'Por favor completa todos los campos obligatorios.')
            return render(request, 'modelo_form.html', {
                'categorias': ModeloML.CATEGORIA_CHOICES,
                'estados': ModeloML.ESTADO_CHOICES,
            })
            
        # Validación estricta de extensiones para simplificar el código
        if not (archivo_modelo.name.endswith('.onnx') or archivo_modelo.name.endswith('.pkl')):
            messages.error(request, 'Error: El archivo del modelo debe ser estrictamente formato .onnx o .pkl')
            return render(request, 'modelo_form.html', {
                'categorias': ModeloML.CATEGORIA_CHOICES,
                'estados': ModeloML.ESTADO_CHOICES,
            })
        
        try:
            modelo = ModeloML.objects.create(
                nombre=nombre,
                nombre_estudio=nombre_estudio,
                descripcion=descripcion,
                categoria=categoria,
                estado=estado,
                precision=precision,
                archivo_modelo=archivo_modelo,
                documento_estudio=documento_estudio,
                img_width=int(img_width) if img_width else 28,
                img_height=int(img_height) if img_height else 28,
                es_rgb=es_rgb,
                invertir_colores=invertir_colores,
                nombres_clases=nombres_clases,
                usuario=request.user,
            )
            messages.success(request, f'¡Modelo "{modelo.nombre}" registrado exitosamente!')
            return redirect('modelos_lista')
        except Exception as e:
            messages.error(request, f'Error al guardar el modelo: {str(e)}')
    
    return render(request, 'modelo_form.html', {
        'categorias': ModeloML.CATEGORIA_CHOICES,
        'estados': ModeloML.ESTADO_CHOICES,
    })


@login_required(login_url='index')
def modelo_detalle(request, pk):
    from app.models import ModeloML
    modelo = get_object_or_404(ModeloML, pk=pk)
    return render(request, 'modelo_detalle.html', {'modelo': modelo})


@login_required(login_url='index')
def modelo_ejecutar(request, pk):
    from app.models import ModeloML
    import os
    from django.conf import settings
    
    modelo = get_object_or_404(ModeloML, pk=pk)
    
    if modelo.estado == 'inactivo':
        messages.error(request, 'Este modelo está inactivo. No se pueden realizar inferencias.')
        return redirect('modelo_detalle', pk=modelo.pk)
    
    resultado = None
    error = None
    
    if request.method == 'POST':
        if 'imagen' not in request.FILES:
            error = "Debes subir una imagen para ejecutar la inferencia."
        else:
            imagen = request.FILES['imagen']
            try:
                # Importar librerías de ML aquí para no recargar todo el servidor si no se usan
                import onnxruntime as ort
                import numpy as np
                from PIL import Image, ImageOps
                
                # Preprocesamiento dinámico basado en las propiedades del ModeloML
                img = Image.open(imagen)
                
                # Convertir a RGB o Grayscale según configuración
                if modelo.es_rgb:
                    img = img.convert('RGB')
                else:
                    img = img.convert('L')
                
                # Invertir colores si aplica (ej. modelos de dígitos manuscritos)
                if modelo.invertir_colores:
                    img = ImageOps.invert(img)
                
                # Redimensionar según dimensiones esperadas
                img = img.resize((modelo.img_width, modelo.img_height), Image.Resampling.LANCZOS)
                
                # Convertir a Numpy Array y normalizar
                img_data = np.array(img).astype('float32') / 255.0
                
                # Descargar o preparar ruta del archivo ONNX
                import tempfile
                import urllib.request
                
                file_url = modelo.archivo_modelo.url
                
                with tempfile.NamedTemporaryFile(delete=False, suffix=".onnx") as tmp_file:
                    if file_url.startswith('http'):
                        urllib.request.urlretrieve(file_url, tmp_file.name)
                        onnx_path = tmp_file.name
                    else:
                        local_path = file_url.replace(settings.MEDIA_URL, '')
                        onnx_path = os.path.join(settings.MEDIA_ROOT, local_path)
                
                # Iniciar la sesión de OnnxRuntime
                session = ort.InferenceSession(onnx_path)
                
                # Obtener info del nodo de entrada
                input_meta = session.get_inputs()[0]
                input_name = input_meta.name
                input_shape = input_meta.shape # Puede ser [None, 3, 224, 224] o [None, 1, 28, 28] etc.
                
                # Adaptar el shape dinámicamente según lo que espere el ONNX
                rank = len(input_shape)
                C = 3 if modelo.es_rgb else 1
                
                if rank == 4:
                    # Pillow `img_data` tiene shape: (H, W, C) si es RGB, y (H, W) si es Grayscale.
                    # Primero estandarizamos a (H, W, C)
                    if not modelo.es_rgb:
                        img_data = np.expand_dims(img_data, axis=-1) # Convierte (H, W) a (H, W, 1)
                        
                    # Autodetección de NCHW (Canales Primero) vs NHWC (Canales Últimos)
                    is_channels_first = True # Por defecto NCHW
                    
                    if input_shape[3] == C or str(input_shape[3]) == str(C):
                        is_channels_first = False # Canales al final (NHWC)
                    elif input_shape[1] == C or str(input_shape[1]) == str(C):
                        is_channels_first = True  # Canales al principio (NCHW)
                    
                    if is_channels_first:
                        # (H, W, C) -> (C, H, W)
                        img_data = np.transpose(img_data, (2, 0, 1))
                        input_data = img_data.reshape(1, C, modelo.img_height, modelo.img_width)
                    else:
                        # Se mantiene (H, W, C) y solo se añade el Batch
                        input_data = img_data.reshape(1, modelo.img_height, modelo.img_width, C)
                        
                elif rank == 3:
                    # Espera [Batch, Height, Width]
                    input_data = img_data.reshape(1, modelo.img_height, modelo.img_width)
                else:
                    # Fallback Flatten a 1D si el modelo es un MLP crudo
                    flat_size = modelo.img_height * modelo.img_width * (3 if modelo.es_rgb else 1)
                    input_data = img_data.reshape(1, flat_size)
                
                # Ejecutar modelo
                result = session.run(None, {input_name: input_data})
                
                # El resultado suele ser log_probs o probabilidades
                log_probs = result[0]
                
                # Obtener la clase con mayor probabilidad (Argmax)
                clase_predicha = np.argmax(log_probs)
                
                # Softmax manual si el modelo tira solo logits crudos (opcional para mostrar % real)
                exp_vals = np.exp(log_probs - np.max(log_probs))
                softmax_probs = exp_vals / np.sum(exp_vals)
                confianza_pct = float(softmax_probs[0][clase_predicha]) * 100
                
                # Mapear nombre humano de clase si está disponible
                clase_nombre = str(clase_predicha)
                if modelo.nombres_clases:
                    nombres = [n.strip() for n in modelo.nombres_clases.split(',')]
                    if 0 <= clase_predicha < len(nombres):
                        clase_nombre = nombres[clase_predicha]

                resultado = {
                    'clase': clase_nombre,
                    'confianza': round(confianza_pct, 2)
                }
                
                # Limpiar archivo temporal si se descargó
                if file_url.startswith('http') and os.path.exists(onnx_path):
                    os.remove(onnx_path)
                    
            except Exception as e:
                error = f"Error durante la inferencia: {str(e)}"
    
    return render(request, 'modelo_ejecutar.html', {
        'modelo': modelo,
        'resultado': resultado,
        'error': error
    })
