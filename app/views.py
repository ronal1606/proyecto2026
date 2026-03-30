"""
views.py — Lógica de negocio de la aplicación AgroVision
=========================================================
Contiene TODAS las vistas (controladores) que procesan peticiones HTTP
y devuelven respuestas HTML a los templates.

Módulos cubiertos:
  1. Autenticación:  index (login), register, logout_view, verify_2fa
  2. Dashboard:      dashboard, nosotros
  3. Módulo ML:      modelos_lista, modelo_crear, modelo_detalle, modelo_ejecutar
"""

# Utilidades de Django para renderizar plantillas y redirigir
from django.shortcuts import render, redirect, get_object_or_404
# Sistema de autenticación de Django
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.models import User
# Decorador para proteger vistas que requieren sesión activa
from django.contrib.auth.decorators import login_required
# Mensajes flash (alertas de éxito, error, info que se muestran al usuario una sola vez)
from django.contrib import messages

# Envío de correo electrónico
from django.core.mail import send_mail
from django.utils import timezone
from datetime import timedelta
from django.conf import settings
import random


# ============================================================
# HELPERS DE ROL
# ============================================================

def es_admin(user):
    """
    Devuelve True si el usuario tiene rol 'admin' en su perfil
    o si es superusuario de Django.
    Se usa para controlar acceso a acciones administrativas.
    """
    try:
        return user.profile.es_admin()
    except Exception:
        return user.is_superuser


# ============================================================
# 1. AUTENTICACIÓN
# ============================================================

def index(request):
    """
    Vista de Login / Página principal.

    Flujo:
      GET  → Renderiza el formulario de inicio de sesión (index.html).
      POST → Autentica credenciales. Si son correctas:
               1. Genera un OTP de 6 dígitos y lo guarda en el perfil del usuario.
               2. Envía el OTP al correo del usuario como HTML.
               3. Guarda el ID del usuario en sesión (pre_2fa_user_id) SIN hacer
                  login permanente todavía.
               4. Redirige a la vista de verificación 2FA (verify_2fa).
             Si son incorrectas, muestra un mensaje de error.
    """
    # Si el usuario ya tiene sesión activa, no tiene sentido mostrarle el login
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        # authenticate() verifica usuario y contraseña contra la base de datos
        user = authenticate(request, username=username, password=password)

        if user is not None:
            # ── Paso 1: Generar OTP ──────────────────────────────────────────
            otp = str(random.randint(100000, 999999))

            # Asegurarse de que el perfil existe (debería crearse por señal, pero por si acaso)
            if not hasattr(user, 'profile'):
                from app.models import UserProfile
                UserProfile.objects.create(user=user)

            # Guardar el OTP y la marca de tiempo en el perfil (para validar expiración luego)
            user.profile.otp_code = otp
            user.profile.otp_created_at = timezone.now()
            user.profile.save()

            # ── Paso 2: Enviar correo con el OTP ────────────────────────────
            from django.template.loader import render_to_string
            from django.utils.html import strip_tags

            subject = '🔑 Tu código de verificación - AgroVision'
            # Renderiza el template email_2fa.html con el nombre y el código OTP
            html_message = render_to_string('email_2fa.html', {
                'nombre': user.first_name or user.username,
                'otp_code': otp
            })
            # Versión plana del correo para clientes que no soporten HTML
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
                # Si el SMTP no está configurado, se avisa al usuario pero no se bloquea el flujo
                messages.error(request, 'Aviso: No se pudo enviar el correo real (revisa tu consola de servidor o configura SMTP en .env).')

            # ── Paso 3: Guardar intención de login y redirigir a 2FA ────────
            # NO se llama a auth_login() aquí — el login definitivo ocurre en verify_2fa
            request.session['pre_2fa_user_id'] = user.id
            return redirect('verify_2fa')
        else:
            messages.error(request, 'Usuario o contraseña incorrectos.')

    return render(request, 'index.html')


def register(request):
    """
    Vista de Registro de nuevos usuarios.

    Flujo:
      GET  → Muestra el formulario de registro (register.html).
      POST → Valida los datos del formulario:
               - Contraseñas coincidentes y con mínimo 8 caracteres.
               - Nombre de usuario y correo únicos (no duplicados en BD).
             Si todo es correcto, crea el usuario y redirige al login.
             Si hay error, muestra mensajes descriptivos y vuelve al formulario.
    """
    # Usuarios ya autenticados no deben poder registrarse de nuevo
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        # Extraer todos los campos del formulario POST
        username = request.POST.get('username')
        email = request.POST.get('email')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')

        # ── Validaciones ─────────────────────────────────────────────────────
        if password1 != password2:
            messages.error(request, 'Las contraseñas no coinciden.')
            return render(request, 'register.html')

        if len(password1) < 8:
            messages.error(request, 'La contraseña debe tener al menos 8 caracteres.')
            return render(request, 'register.html')

        # Verificar unicidad en la base de datos
        if User.objects.filter(username=username).exists():
            messages.error(request, 'El nombre de usuario ya está en uso.')
            return render(request, 'register.html')

        if User.objects.filter(email=email).exists():
            messages.error(request, 'El correo electrónico ya está registrado.')
            return render(request, 'register.html')

        # ── Crear usuario ─────────────────────────────────────────────────────
        try:
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password1,       # create_user hashea automáticamente la contraseña
                first_name=first_name,
                last_name=last_name
            )
            user.save()

            messages.success(request, '¡Cuenta creada exitosamente! Por favor inicia sesión.')
            return redirect('index')

        except Exception as e:
            messages.error(request, f'Error al crear la cuenta: {str(e)}')

    return render(request, 'register.html')


# ── Decorador @login_required ────────────────────────────────────────────────
# Todas las vistas marcadas con este decorador redirigen a 'index' (login)
# si el usuario no tiene sesión activa, protegiendo el acceso.

@login_required(login_url='index')
def dashboard(request):
    """
    Panel principal del usuario autenticado.

    Muestra estadísticas básicas calculadas desde la base de datos:
      - modelos_activos:     Modelos con estado='activo'.
      - experimentos_doc:    Modelos que tienen documento de estudio adjunto.
      - ejecuciones_totales: Estimación simulada (modelos × 12).
    """
    from app.models import ModeloML, HistorialEjecucion

    # Conteo de modelos activos (los que se pueden ejecutar en producción)
    modelos_activos = ModeloML.objects.filter(estado='activo').count()
    # Modelos que tienen un documento PDF de estudios académicos adjunto
    experimentos_doc = ModeloML.objects.exclude(documento_estudio='').count()
    # Total real de ejecuciones registradas en el historial
    ejecuciones_totales = HistorialEjecucion.objects.count()

    context = {
        'modelos_activos': modelos_activos,
        'experimentos_doc': experimentos_doc,
        'ejecuciones_totales': ejecuciones_totales,
    }
    return render(request, 'dashboard.html', context)


@login_required(login_url='index')
def logout_view(request):
    """
    Cierra la sesión del usuario actual usando auth_logout() de Django,
    muestra un mensaje de confirmación y redirige al login.
    """
    auth_logout(request)
    messages.success(request, 'Has cerrado sesión correctamente.')
    return redirect('index')


@login_required(login_url='index')
def nosotros(request):
    """
    Página de información del semillero AgroVision.
    Solo renderiza el template estático nosotros.html.
    """
    return render(request, 'nosotros.html')


def verify_2fa(request):
    """
    Verificación del segundo factor de autenticación (OTP por correo).

    Flujo:
      - Lee el ID de usuario guardado en sesión (pre_2fa_user_id) por la vista index().
      - Si no existe, redirige al login (sesión inválida o expirada).
      GET  → Muestra el formulario de ingreso del código OTP, con el correo enmascarado.
      POST → Valida el código:
               1. Verifica que existe un código OTP pendiente.
               2. Verifica que no haya expirado (límite: 5 minutos).
               3. Compara el código ingresado con el almacenado.
             Si es correcto → llama a auth_login() para iniciar sesión permanente
             y redirige al dashboard.
             Si es incorrecto → muestra mensaje de error.
    """
    # Recuperar el ID del usuario que está en proceso de login 2FA
    user_id = request.session.get('pre_2fa_user_id')
    if not user_id:
        # Sin este dato en sesión, no hay contexto de 2FA válido
        return redirect('index')

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return redirect('index')

    if request.method == 'POST':
        entered_code = request.POST.get('otp_code')

        # ── Validar que el OTP existe ────────────────────────────────────────
        if not hasattr(user, 'profile') or not user.profile.otp_code or not user.profile.otp_created_at:
            messages.error(request, 'No hay código pendiente de verificación.')
            return redirect('index')

        # ── Verificar expiración: máximo 5 minutos desde la generación ───────
        if timezone.now() > user.profile.otp_created_at + timedelta(minutes=5):
            messages.error(request, 'El código de verificación ha expirado. Por favor, inicia sesión de nuevo.')
            # Limpiar el OTP ya expirado para evitar reutilización
            user.profile.otp_code = None
            user.profile.save()
            try:
                del request.session['pre_2fa_user_id']
            except KeyError:
                pass
            return redirect('index')

        # ── Comparar el código ingresado con el almacenado ───────────────────
        if entered_code == user.profile.otp_code:
            # ✅ Código correcto: limpiar OTP y establecer sesión permanente
            user.profile.otp_code = None
            user.profile.save()
            try:
                del request.session['pre_2fa_user_id']
            except KeyError:
                pass

            # Aquí sí se hace el login definitivo en Django
            auth_login(request, user)
            messages.success(request, f'¡Bienvenido de vuelta, {user.first_name or user.username}!', extra_tags='success')
            return redirect('dashboard')
        else:
            messages.error(request, 'El código de verificación es incorrecto.')

    # ── Enmascarar el correo para mostrar en el template (ej: r****l@gmail.com) ──
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


# ============================================================
# 2. MÓDULO DE CATÁLOGO DE MODELOS ML
# ============================================================

@login_required(login_url='index')
def modelos_lista(request):
    """
    Lista/Catálogo de todos los modelos ML registrados.
    Las categorías para el filtro se obtienen dinámicamente de la BD.
    La búsqueda por texto filtra nombre, nombre_estudio y descripción.
    """
    from app.models import ModeloML, Categoria

    query = request.GET.get('q', '')
    categoria = request.GET.get('categoria', '')

    modelos = ModeloML.objects.all().order_by('-fecha_creacion')

    if query:
        modelos = (
            modelos.filter(nombre__icontains=query) |
            modelos.filter(nombre_estudio__icontains=query) |
            modelos.filter(descripcion__icontains=query)
        )
    if categoria:
        modelos = modelos.filter(categoria__iexact=categoria)

    # Obtener las categorías que realmente existen en modelos registrados
    categorias_en_uso = (
        ModeloML.objects.values_list('categoria', flat=True)
        .distinct()
        .order_by('categoria')
    )

    return render(request, 'modelos_lista.html', {
        'modelos': modelos,
        'categorias': categorias_en_uso,
        'query': query,
        'categoria_activa': categoria,
    })


@login_required(login_url='index')
def modelo_crear(request):
    """
    Registrar un nuevo modelo ML en el catálogo.

    Flujo:
      GET  → Muestra el formulario vacío (modelo_form.html) con los choices de
             categoría y estado cargados desde el modelo.
      POST → Extrae todos los campos del formulario, aplica validaciones y crea
             el registro en base de datos.

    Campos del formulario:
      Básicos:   nombre, nombre_estudio, descripcion, categoria, estado, precision.
      Archivos:  archivo_modelo (.onnx/.pkl), documento_estudio (PDF).
      Inferencia: img_width, img_height, es_rgb, invertir_colores, nombres_clases.

    Validaciones:
      - Todos los campos básicos y el archivo del modelo son obligatorios.
      - El archivo del modelo debe ser .onnx o .pkl (validación de extensión).
    """
    from app.models import ModeloML

    # Solo los administradores pueden subir/registrar modelos
    if not es_admin(request.user):
        messages.error(request, 'No tienes permisos para agregar modelos. Contacta a un administrador.')
        return redirect('modelos_lista')

    if request.method == 'POST':
        # ── Extraer datos del formulario ─────────────────────────────────────
        nombre = request.POST.get('nombre')
        nombre_estudio = request.POST.get('nombre_estudio')
        descripcion = request.POST.get('descripcion')
        categoria = request.POST.get('categoria')
        estado = request.POST.get('estado', 'activo')
        # precision es opcional; si viene vacío se guarda como None (NULL en BD)
        precision = request.POST.get('precision') or None
        # Archivos subidos (request.FILES en lugar de request.POST)
        archivo_modelo = request.FILES.get('archivo_modelo')
        documento_estudio = request.FILES.get('documento_estudio')

        # ── Metadatos de inferencia ──────────────────────────────────────────
        img_width = request.POST.get('img_width', 28)
        img_height = request.POST.get('img_height', 28)
        # Los checkboxes HTML envían 'on' si marcados, nada si no marcados
        es_rgb = request.POST.get('es_rgb') == 'on'
        invertir_colores = request.POST.get('invertir_colores') == 'on'
        # Nombres de clases separados por coma: "Sano, Enfermo, Muerto"
        nombres_clases = request.POST.get('nombres_clases', '')

        # ── Validar campos obligatorios ──────────────────────────────────────
        if not nombre or not nombre_estudio or not descripcion or not categoria or not archivo_modelo:
            messages.error(request, 'Por favor completa todos los campos obligatorios.')
            return render(request, 'modelo_form.html', {
                'categorias': ModeloML.CATEGORIA_CHOICES,
                'estados': ModeloML.ESTADO_CHOICES,
            })

        # ── Validar extensión del archivo de modelo ──────────────────────────
        if not (archivo_modelo.name.endswith('.onnx') or archivo_modelo.name.endswith('.pkl')):
            messages.error(request, 'Error: El archivo del modelo debe ser estrictamente formato .onnx o .pkl')
            return render(request, 'modelo_form.html', {
                'categorias': ModeloML.CATEGORIA_CHOICES,
                'estados': ModeloML.ESTADO_CHOICES,
            })

        # ── Crear el registro en base de datos ───────────────────────────────
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
                # Convertir a entero con fallback a 28 en caso de valor vacío
                img_width=int(img_width) if img_width else 28,
                img_height=int(img_height) if img_height else 28,
                es_rgb=es_rgb,
                invertir_colores=invertir_colores,
                nombres_clases=nombres_clases,
                usuario=request.user,   # Asociar con el usuario que lo registra
            )
            messages.success(request, f'¡Modelo "{modelo.nombre}" registrado exitosamente!')
            return redirect('modelos_lista')
        except Exception as e:
            messages.error(request, f'Error al guardar el modelo: {str(e)}')

    # GET: renderizar formulario
    return render(request, 'modelo_form.html', {
        'categorias': __import__('app.models', fromlist=['Categoria']).Categoria.objects.all(),
        'estados': ModeloML.ESTADO_CHOICES,
    })


@login_required(login_url='index')
def modelo_detalle(request, pk):
    """
    Vista de detalle de un modelo ML específico.

    Parámetros:
      pk (int): Clave primaria del modelo en la base de datos.

    Usa get_object_or_404 para devolver 404 automáticamente si el ID no existe.
    Renderiza modelo_detalle.html con el objeto completo del modelo.
    """
    from app.models import ModeloML
    modelo = get_object_or_404(ModeloML, pk=pk)
    return render(request, 'modelo_detalle.html', {
        'modelo': modelo,
        'es_admin': es_admin(request.user),
    })


@login_required(login_url='index')
def modelo_editar(request, pk):
    """
    Editar los datos de un modelo ML existente.

    Solo disponible para usuarios con rol 'admin'.
    GET  → Muestra el formulario pre-poblado con los datos actuales.
    POST → Valida y guarda los cambios. Si se sube un nuevo archivo
            reemplaza el anterior; si se deja en blanco, conserva el original.
    """
    from app.models import ModeloML, Categoria

    if not es_admin(request.user):
        messages.error(request, 'No tienes permisos para editar modelos.')
        return redirect('modelos_lista')

    modelo = get_object_or_404(ModeloML, pk=pk)

    if request.method == 'POST':
        nombre        = request.POST.get('nombre')
        nombre_estudio= request.POST.get('nombre_estudio')
        descripcion   = request.POST.get('descripcion')
        categoria_sel = request.POST.get('categoria')
        categoria_nueva = request.POST.get('categoria_nueva', '').strip()
        estado        = request.POST.get('estado', 'activo')
        precision     = request.POST.get('precision') or None
        img_width     = request.POST.get('img_width', 28)
        img_height    = request.POST.get('img_height', 28)
        es_rgb_val    = request.POST.get('es_rgb') == 'on'
        invertir      = request.POST.get('invertir_colores') == 'on'
        nombres_clases= request.POST.get('nombres_clases', '')

        # Resolver categoría, igual que en modelo_crear
        if categoria_sel == 'otro':
            if not categoria_nueva:
                messages.error(request, 'Debes escribir el nombre de la nueva categoría.')
            else:
                cat_obj, _ = Categoria.objects.get_or_create(nombre=categoria_nueva.lower())
                categoria_final = cat_obj.nombre
        else:
            categoria_final = categoria_sel
            Categoria.objects.get_or_create(nombre=categoria_final)

        if not nombre or not nombre_estudio or not descripcion or not categoria_final:
            messages.error(request, 'Por favor completa todos los campos obligatorios.')
        else:
            modelo.nombre          = nombre
            modelo.nombre_estudio  = nombre_estudio
            modelo.descripcion     = descripcion
            modelo.categoria       = categoria_final
            modelo.estado          = estado
            modelo.precision       = precision
            modelo.img_width       = int(img_width) if img_width else 28
            modelo.img_height      = int(img_height) if img_height else 28
            modelo.es_rgb          = es_rgb_val
            modelo.invertir_colores= invertir
            modelo.nombres_clases  = nombres_clases

            nuevo_archivo = request.FILES.get('archivo_modelo')
            nuevo_doc     = request.FILES.get('documento_estudio')
            if nuevo_archivo:
                modelo.archivo_modelo = nuevo_archivo
            if nuevo_doc:
                modelo.documento_estudio = nuevo_doc

            modelo.save()
            messages.success(request, f'Modelo "{modelo.nombre}" actualizado correctamente.')
            return redirect('modelo_detalle', pk=pk)

    return render(request, 'modelo_form.html', {
        'categorias': Categoria.objects.all(),
        'estados'   : ModeloML.ESTADO_CHOICES,
        'modelo'    : modelo,
        'modo_editar': True,
    })


@login_required(login_url='index')
def modelo_eliminar(request, pk):
    """
    Eliminar un modelo ML del catálogo.

    Solo acepta POST (el botón de confirmación del modal envía el form).
    Solo disponible para usuarios con rol 'admin'.
    Después de eliminar, redirige a la lista de modelos con un mensaje de éxito.
    Las señales de post_delete en models.py se encargan de borrar los archivos
    del almacenamiento (Azure/local) automáticamente.
    """
    from app.models import ModeloML

    if not es_admin(request.user):
        messages.error(request, 'No tienes permisos para eliminar modelos.')
        return redirect('modelos_lista')

    modelo = get_object_or_404(ModeloML, pk=pk)

    if request.method == 'POST':
        nombre = modelo.nombre
        modelo.delete()
        messages.success(request, f'Modelo "{nombre}" eliminado correctamente.')
        return redirect('modelos_lista')

    # Si alguien intenta GET, redirigir al detalle
    return redirect('modelo_detalle', pk=pk)



@login_required(login_url='index')
def modelo_ejecutar(request, pk):
    """
    Motor de inferencia en línea usando ONNX Runtime.

    Permite al usuario subir una imagen, preprocesarla y obtener la predicción
    del modelo ONNX almacenado en la base de datos.

    Parámetros:
      pk (int): Clave primaria del modelo a ejecutar.

    Flujo completo (POST):
      1. Verificar que el modelo no esté inactivo.
      2. Leer la imagen subida con Pillow.
      3. Preprocesar según la configuración del modelo:
           - Convertir a RGB o Grayscale.
           - Invertir colores si se requiere (ej: dígitos MNIST fondo blanco).
           - Redimensionar a las dimensiones esperadas (img_width × img_height).
           - Normalizar píxeles al rango [0, 1].
      4. Adaptar la forma (shape) del tensor al formato que espera el ONNX:
           - Rank 4 → imagen 2D con batch y canales (NCHW o NHWC detectado automático).
           - Rank 3 → imagen 2D sin canal explícito.
           - Rank 2 → vector aplanado (MLP tabular).
      5. Ejecutar la sesión ONNX (session.run()).
      6. Postprocesar resultados:
           - Argmax para obtener la clase predicha.
           - Softmax manual para convertir logits crudos a probabilidades (%).
           - Mapear el índice de clase a su nombre humano (si nombres_clases está configurado).
      7. Devolver resultado al template: {'clase': ..., 'confianza': ...}.

    Variables de contexto del template:
      modelo:    Objeto ModeloML con toda la info del modelo.
      resultado: Dict {'clase': str, 'confianza': float} — None si aún no se ejecutó.
      error:     Mensaje de error en cadena — None si no hubo error.
    """
    from app.models import ModeloML
    import os
    from django.conf import settings

    # Obtener el modelo o retornar 404 si no existe
    modelo = get_object_or_404(ModeloML, pk=pk)

    # ── Guardia: modelos inactivos no pueden ejecutarse ───────────────────────
    if modelo.estado == 'inactivo':
        messages.error(request, 'Este modelo está inactivo. No se pueden realizar inferencias.')
        return redirect('modelo_detalle', pk=modelo.pk)

    resultado = None   # Resultado de la predicción (diccionario)
    error = None       # Mensaje de error para mostrar en el template

    if request.method == 'POST':
        # ── Validar que se subió una imagen ──────────────────────────────────
        if 'imagen' not in request.FILES:
            error = "Debes subir una imagen para ejecutar la inferencia."
        else:
            imagen = request.FILES['imagen']
            try:
                # Importar librerías pesadas solo cuando se necesitan (no al arrancar el servidor)
                import onnxruntime as ort
                import numpy as np
                from PIL import Image, ImageOps

                # ── Paso 1: Abrir imagen con Pillow ──────────────────────────
                img = Image.open(imagen)

                # ── Paso 2: Convertir espacio de color ────────────────────────
                # 'RGB'  → 3 canales (rojo, verde, azul)
                # 'L'    → 1 canal (escala de grises)
                if modelo.es_rgb:
                    img = img.convert('RGB')
                else:
                    img = img.convert('L')

                # ── Paso 3: Invertir colores si el modelo lo requiere ─────────
                # Útil para modelos entrenados con MNIST donde los dígitos
                # son blancos sobre fondo negro, pero la foto capturada suele
                # tener fondo claro y trazos oscuros.
                if modelo.invertir_colores:
                    img = ImageOps.invert(img)

                # ── Paso 4: Redimensionar al tamaño que espera el modelo ──────
                # LANCZOS es un filtro de alta calidad para reducción de imágenes
                img = img.resize((modelo.img_width, modelo.img_height), Image.Resampling.LANCZOS)

                # ── Paso 5: Convertir a NumPy y normalizar [0, 255] → [0.0, 1.0] ──
                img_data = np.array(img).astype('float32') / 255.0

                # ── Paso 6: Resolver la ruta del archivo ONNX ─────────────────
                import tempfile
                import urllib.request

                file_url = modelo.archivo_modelo.url

                with tempfile.NamedTemporaryFile(delete=False, suffix=".onnx") as tmp_file:
                    if file_url.startswith('http'):
                        # El archivo está en almacenamiento remoto (ej: S3, CDN)
                        urllib.request.urlretrieve(file_url, tmp_file.name)
                        onnx_path = tmp_file.name
                    else:
                        # El archivo está en MEDIA_ROOT local del servidor
                        local_path = file_url.replace(settings.MEDIA_URL, '')
                        onnx_path = os.path.join(settings.MEDIA_ROOT, local_path)

                # ── Paso 7: Crear sesión de ONNX Runtime ──────────────────────
                # InferenceSession carga el modelo ONNX en memoria y lo optimiza
                session = ort.InferenceSession(onnx_path)

                # Obtener metadatos del nodo de entrada del grafo ONNX
                input_meta = session.get_inputs()[0]
                input_name = input_meta.name           # Nombre del tensor de entrada (ej: 'input')
                input_shape = input_meta.shape         # Forma esperada (ej: [None, 3, 224, 224])

                # ── Paso 8: Adaptar el tensor de imagen al shape del modelo ───
                rank = len(input_shape)           # Número de dimensiones del tensor
                C = 3 if modelo.es_rgb else 1    # Número de canales (3=RGB, 1=Grayscale)

                if rank == 4:
                    # Caso más común: imagen con batch y canal explícito
                    # Pillow devuelve (H, W, C) para RGB y (H, W) para Grayscale
                    if not modelo.es_rgb:
                        # Añadir dimensión de canal: (H, W) → (H, W, 1)
                        img_data = np.expand_dims(img_data, axis=-1)

                    # Autodetectar si el modelo espera NCHW o NHWC comparando shapes
                    is_channels_first = True  # Asumimos NCHW por defecto (PyTorch/ONNX estándar)

                    if input_shape[3] == C or str(input_shape[3]) == str(C):
                        # El 4° elemento es el número de canales → el modelo espera NHWC (TensorFlow style)
                        is_channels_first = False
                    elif input_shape[1] == C or str(input_shape[1]) == str(C):
                        # El 2° elemento es el número de canales → el modelo espera NCHW (PyTorch style)
                        is_channels_first = True

                    if is_channels_first:
                        # Convertir (H, W, C) → (C, H, W) → (1, C, H, W) con batch
                        img_data = np.transpose(img_data, (2, 0, 1))
                        input_data = img_data.reshape(1, C, modelo.img_height, modelo.img_width)
                    else:
                        # Mantener (H, W, C) y añadir batch: → (1, H, W, C)
                        input_data = img_data.reshape(1, modelo.img_height, modelo.img_width, C)

                elif rank == 3:
                    # El modelo espera [Batch, Height, Width] sin canal explícito
                    input_data = img_data.reshape(1, modelo.img_height, modelo.img_width)
                else:
                    # Fallback: el modelo es un MLP que espera un vector 1D
                    # Aplanar todos los píxeles en un solo vector
                    flat_size = modelo.img_height * modelo.img_width * (3 if modelo.es_rgb else 1)
                    input_data = img_data.reshape(1, flat_size)

                # ── Paso 9: Ejecutar el modelo ONNX ───────────────────────────
                # session.run(None, {input_name: input_data}) devuelve lista de tensores
                result = session.run(None, {input_name: input_data})

                # ── Paso 10: Postprocesar la salida ───────────────────────────
                # result[0] contiene el tensor de salida principal
                # Puede ser logits crudos (antes de softmax) o probabilidades
                log_probs = result[0]

                # Argmax: encontrar el índice de la clase con mayor puntuación
                clase_predicha = np.argmax(log_probs)

                # Softmax manual para convertir logits a probabilidades reales
                # Se resta el máximo antes de exp() para estabilidad numérica
                exp_vals = np.exp(log_probs - np.max(log_probs))
                softmax_probs = exp_vals / np.sum(exp_vals)
                confianza_pct = float(softmax_probs[0][clase_predicha]) * 100

                # ── Paso 11: Mapear índice numérico a nombre de clase ─────────
                # Por defecto se muestra el número (0, 1, 2...)
                clase_nombre = str(clase_predicha)
                if modelo.nombres_clases:
                    # Parsear la cadena "Sano, Enfermo, Muerto" a lista ['Sano', 'Enfermo', 'Muerto']
                    nombres = [n.strip() for n in modelo.nombres_clases.split(',')]
                    if 0 <= clase_predicha < len(nombres):
                        clase_nombre = nombres[clase_predicha]

                # Empaquetar el resultado final para el template
                resultado = {
                    'clase': clase_nombre,
                    'confianza': round(confianza_pct, 2)
                }

                # ── Guardar en historial de ejecuciones ───────────────────────
                # La imagen original se sube al almacenamiento (Azure/local)
                # junto con la ubicación y el resultado textual.
                try:
                    from app.models import HistorialEjecucion
                    ubicacion = request.POST.get('ubicacion', '').strip()
                    # Rewind the file to read it again for storage
                    imagen.seek(0)
                    HistorialEjecucion.objects.create(
                        usuario=request.user,
                        modelo=modelo,
                        imagen=imagen,
                        ubicacion=ubicacion,
                        resultado=f"{clase_nombre} ({round(confianza_pct, 2)}%)"
                    )
                except Exception as hist_err:
                    # Guardar historial es no-bloqueante: si falla, no interrumpimos la inferencia
                    pass

                # ── Limpieza: borrar archivo temporal si se descargó ──────────
                if file_url.startswith('http') and os.path.exists(onnx_path):
                    os.remove(onnx_path)

            except Exception as e:
                error = f"Error durante la inferencia: {str(e)}"

    return render(request, 'modelo_ejecutar.html', {
        'modelo': modelo,
        'resultado': resultado,
        'error': error
    })


# ============================================================
# 3. PÁGINA 404 PERSONALIZADA
# ============================================================

def pagina_404(request, exception):
    """
    Handler personalizado para errores 404 (página no encontrada).

    Django llama automáticamente a esta función cuando ninguna URL
    coincide con la ruta solicitada, siempre que DEBUG=False y
    handler404 esté configurado en urls.py del proyecto.
    Renderiza el template 404.html con el código HTTP 404.
    """
    return render(request, '404.html', status=404)


def ruta_no_encontrada(request):
    """
    Vista catch-all: captura cualquier URL no definida en urlpatterns.
    Renderiza la plantilla 404.html con código de estado 404.
    """
    return render(request, '404.html', status=404)


# ============================================================
# 4. HISTORIAL DE EJECUCIONES
# ============================================================

@login_required(login_url='index')
def historial_lista(request):
    """
    Muestra el historial de ejecuciones del usuario (o de todos los usuarios si es admin).
    Soporta paginación: el usuario puede elegir ver 5, 10 o 25 registros por página.
    El admin ve todos los registros con el nombre del usuario que ejecutó.
    """
    from app.models import HistorialEjecucion
    from django.core.paginator import Paginator

    if es_admin(request.user):
        qs = HistorialEjecucion.objects.select_related('usuario', 'modelo').all()
    else:
        qs = HistorialEjecucion.objects.select_related('usuario', 'modelo').filter(usuario=request.user)

    per_page = int(request.GET.get('per_page', 10))
    if per_page not in [5, 10, 25]:
        per_page = 10

    paginator = Paginator(qs, per_page)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    return render(request, 'historial_lista.html', {
        'page_obj': page_obj,
        'per_page': per_page,
        'total': qs.count(),
        'es_admin': es_admin(request.user),
    })


@login_required(login_url='index')
def historial_detalle(request, pk):
    """
    Muestra toda la información de una ejecución en detalle:
    imagen completa, resultado, ubicación, modelo y fecha.
    Los usuarios solo pueden ver las suyas; el admin puede ver cualquiera.
    """
    from app.models import HistorialEjecucion

    historial = get_object_or_404(HistorialEjecucion, pk=pk)

    # Verificar que el user sólo accede a lo suyo (admin puede ver todo)
    if not es_admin(request.user) and historial.usuario != request.user:
        messages.error(request, 'No tienes permiso para ver esta ejecución.')
        return redirect('historial_lista')

    return render(request, 'historial_detalle.html', {
        'historial': historial,
        'es_admin': es_admin(request.user),
    })


@login_required(login_url='index')
def historial_eliminar(request, pk):
    """
    Elimina un registro de historial de ejecución.
    El usuario solo puede eliminar los suyos; el admin puede eliminar cualquiera.
    Solo acepta POST para evitar eliminaciones accidentales por GET.
    La señal post_delete del modelo borra la imagen del almacenamiento automáticamente.
    """
    from app.models import HistorialEjecucion

    historial = get_object_or_404(HistorialEjecucion, pk=pk)

    if not es_admin(request.user) and historial.usuario != request.user:
        messages.error(request, 'No tienes permiso para eliminar esta ejecución.')
        return redirect('historial_lista')

    if request.method == 'POST':
        historial.delete()
        messages.success(request, 'Ejecución eliminada del historial correctamente.')
        return redirect('historial_lista')

    return redirect('historial_detalle', pk=pk)
