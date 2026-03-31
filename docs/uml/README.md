# Diagramas de Casos de Uso UML — AgroVision

Este directorio contiene los diagramas de casos de uso UML del sistema **AgroVision**, una plataforma web para la gestión e inferencia de modelos de Machine Learning aplicados a la agricultura.

---

## Actores del Sistema

| Actor | Descripción |
|-------|-------------|
| **Usuario No Autenticado** | Visitante que aún no ha iniciado sesión. Puede registrarse o autenticarse. |
| **Usuario Autenticado** | Usuario con sesión activa. Puede explorar modelos, ejecutar inferencias y ver su historial. |
| **Administrador** | Usuario con rol de admin o superusuario. Hereda todas las capacidades del Usuario Autenticado y además puede gestionar modelos ML. |
| **Sistema de Email (SMTP)** | Actor externo. Recibe la solicitud del sistema para enviar el código OTP de autenticación de dos factores. |
| **Motor ONNX Runtime** | Actor externo. Ejecuta la inferencia sobre el tensor de entrada generado a partir de la imagen del usuario. |

---

## Archivos de Diagramas

| Archivo | Módulo | Descripción |
|---------|--------|-------------|
| [`uc_general.puml`](uc_general.puml) | Sistema Completo | Diagrama general con todos los actores, módulos y casos de uso del sistema. |
| [`uc_autenticacion.puml`](uc_autenticacion.puml) | Autenticación | Login, registro, verificación 2FA y cierre de sesión. |
| [`uc_gestion_modelos.puml`](uc_gestion_modelos.puml) | Gestión de Modelos ML | Crear, editar, eliminar y buscar modelos (Admin). |
| [`uc_inferencia.puml`](uc_inferencia.puml) | Inferencia | Pipeline completo de ejecución de inferencia sobre imágenes. |
| [`uc_historial.puml`](uc_historial.puml) | Historial de Ejecuciones | Ver, detallar y eliminar registros del historial. |

---

## Catálogo de Casos de Uso

### Módulo 1 — Autenticación

| ID | Caso de Uso | Actor Principal | Descripción |
|----|-------------|-----------------|-------------|
| UC01 | Iniciar Sesión | Usuario No Autenticado | Ingresa usuario y contraseña; si válidos, el sistema genera un OTP y redirige a la verificación 2FA. |
| UC02 | Registrarse | Usuario No Autenticado | Completa formulario con usuario, email, nombre y contraseña. El sistema valida unicidad y crea el perfil con rol `user`. |
| UC03 | Verificar Código 2FA | Usuario No Autenticado | Ingresa el código OTP de 6 dígitos recibido por email. El código expira en 5 minutos. |
| UC03a | Generar OTP de 6 Dígitos | Sistema | Genera el código OTP e inicia el temporizador de expiración (5 min). *(include de UC01)* |
| UC03b | Enviar OTP por Email | Sistema / Email | Envía el OTP al correo del usuario mediante SMTP. *(include de UC03a)* |
| UC03c | Reenviar Código OTP | Usuario No Autenticado | Solicita un nuevo OTP en caso de no haber recibido o expirado el anterior. *(extend de UC03)* |
| UC04 | Cerrar Sesión | Usuario Autenticado | Invalida la sesión activa y redirige al login. |

---

### Módulo 2 — Panel Principal

| ID | Caso de Uso | Actor Principal | Descripción |
|----|-------------|-----------------|-------------|
| UC05 | Ver Dashboard | Usuario Autenticado | Visualiza estadísticas del sistema: modelos activos, documentos de investigación y total de ejecuciones. Accede a acciones rápidas. |
| UC06 | Ver Página Nosotros | Usuario Autenticado | Visualiza información del proyecto, semillero y equipo. |

---

### Módulo 3 — Gestión de Modelos ML *(Administrador)*

| ID | Caso de Uso | Actor Principal | Descripción |
|----|-------------|-----------------|-------------|
| UC07 | Ver Catálogo de Modelos | Usuario Autenticado | Lista todos los modelos con nombre, categoría, estado y precisión. Incluye búsqueda y filtros. |
| UC08 | Crear Modelo ML | Administrador | Registra un nuevo modelo ONNX/PKL con sus parámetros de inferencia (dimensiones, espacio de color, clases, etc.) y opcionalmente un PDF del estudio. |
| UC09 | Ver Detalle de Modelo | Usuario Autenticado | Muestra todos los campos del modelo, enlaces de descarga del archivo y del PDF de estudio. |
| UC10 | Editar Modelo ML | Administrador | Actualiza cualquier campo del modelo; los archivos anteriores se eliminan al reemplazarlos. |
| UC11 | Eliminar Modelo ML | Administrador | Elimina el registro de la base de datos y los archivos del almacenamiento. |
| UC12 | Buscar / Filtrar Modelos | Usuario Autenticado | Búsqueda por texto libre (nombre, nombre de estudio, descripción) y/o filtro por categoría de cultivo. |
| UC13 | Gestionar Categorías | Administrador | Añade categorías personalizadas al crear o editar un modelo. Categorías predefinidas: fresa, cacao, manzana, tomate, café, plátano, palma. |

---

### Módulo 4 — Inferencia de Modelos

| ID | Caso de Uso | Actor Principal | Descripción |
|----|-------------|-----------------|-------------|
| UC20 | Ejecutar Inferencia sobre Imagen | Usuario Autenticado | Flujo principal: sube una imagen del cultivo, ingresa la ubicación/campo, y el sistema retorna la clase predicha con su porcentaje de confianza. |
| UC21 | Subir Imagen del Cultivo | Usuario Autenticado | Selecciona y sube la imagen (JPG/PNG/WEBP); el sistema muestra un preview en tiempo real. *(include de UC20)* |
| UC22 | Preprocesar Imagen | Sistema | Pipeline automático: conversión de espacio de color, inversión de colores, redimensionamiento a las dimensiones del modelo y normalización de píxeles [0-255] → [0.0, 1.0]. *(include de UC20)* |
| UC23 | Adaptar Tensor de Entrada | Sistema | Detecta y aplica el formato NCHW (PyTorch) o NHWC (TensorFlow) y el rango adecuado (4, 3 o 2) según el modelo. *(include de UC22)* |
| UC24 | Ejecutar Motor de Inferencia ONNX | Sistema / ONNX Runtime | Carga el modelo desde almacenamiento local o Azure Blob, ejecuta la sesión de ONNX Runtime y obtiene el vector de salida. *(include de UC20)* |
| UC25 | Calcular Resultado y Confianza | Sistema | Aplica ArgMax para la clase predicha y Softmax para las probabilidades; mapea el índice al nombre de clase legible. *(include de UC24)* |
| UC26 | Guardar en Historial de Ejecuciones | Sistema | Persiste el registro de inferencia: usuario, modelo, imagen, ubicación, resultado y timestamp. *(include de UC20)* |

---

### Módulo 5 — Historial de Ejecuciones

| ID | Caso de Uso | Actor Principal | Descripción |
|----|-------------|-----------------|-------------|
| UC30 | Ver Historial de Ejecuciones | Usuario Autenticado | Lista las ejecuciones propias (o todas las del sistema si es admin). Paginable: 5, 10 o 25 registros por página. |
| UC31 | Paginar Historial | Usuario Autenticado | Selecciona la cantidad de registros por página. *(include de UC30)* |
| UC32 | Ver Detalle de Ejecución | Usuario Autenticado | Muestra el registro completo: imagen original, modelo, resultado, ubicación, fecha y usuario. |
| UC33 | Eliminar Entrada de Historial | Usuario Autenticado | Elimina el registro de la BD y la imagen del almacenamiento. Los usuarios eliminan solo los suyos; los admins pueden eliminar cualquiera. |
| UC34 | Ver / Descargar Imagen Subida | Usuario Autenticado | Desde el detalle, visualiza o descarga la imagen original usada en la inferencia. *(extend de UC32)* |

---

## Cómo Renderizar los Diagramas

### Opción 1 — Visual Studio Code
1. Instala la extensión **PlantUML** (`jebbs.plantuml`).
2. Abre cualquier archivo `.puml`.
3. Presiona `Alt+D` (o `Option+D` en macOS) para previsualizar.

### Opción 2 — IntelliJ / PyCharm
1. Instala el plugin **PlantUML Integration**.
2. Abre el archivo `.puml` y el diagrama se renderiza automáticamente.

### Opción 3 — Online
1. Visita [https://www.plantuml.com/plantuml/uml/](https://www.plantuml.com/plantuml/uml/)
2. Pega el contenido de cualquier archivo `.puml`.
3. El diagrama se genera en tiempo real.

### Opción 4 — CLI (requiere Java y PlantUML JAR)
```bash
java -jar plantuml.jar docs/uml/*.puml
```
Genera imágenes PNG en el mismo directorio.

---

## Relaciones UML Utilizadas

| Símbolo | Tipo | Descripción |
|---------|------|-------------|
| `..>` con `<<include>>` | Include | El caso de uso base **siempre** incluye el comportamiento del caso incluido. |
| `..>` con `<<extend>>` | Extend | El caso de uso extensor **puede** añadir comportamiento bajo una condición específica. |
| `-\|>` | Generalización | El actor hijo hereda todas las capacidades del actor padre. |
| `-->` | Asociación | El actor participa directamente en el caso de uso. |
