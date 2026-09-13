# Seguridad, privacidad y límites

## Separación de funciones

`mammoapp/guidance.py` no importa el modelo ni recibe puntuaciones, mapas, imágenes o respuestas de un LLM. Sus entradas son señales declaradas, categoría del informe confirmada y fechas introducidas por el usuario. No determina cuánto tiempo es seguro esperar. El nivel más alto activado tiene prioridad; añadir una señal afirmativa no reduce el nivel.

La interfaz distingue una perspectiva académica y una de comprensión. Esa distinción es visual: no impide que un usuario cambie de perspectiva. La autenticación y la autorización deben configurarse en el alojamiento, con control institucional antes de usar datos que no sean sintéticos.

## Datos que se aceptan

Solo material sintético o desidentificado y autorizado. Se solicita declaración antes de la carga. Límite: 64 MiB por imagen, cuatro archivos por caso, 128 MiB agregados. Máximo 8192 píxeles por lado y 32 millones de píxeles. TIFF multipágina, tomosíntesis y animaciones se rechazan.

DICOM: lector acotado a mamografía 2D en monocromo, 8/16 bits, transferencias little-endian explícita o implícita admitidas. Se rechazan compresión, modalidades/SOP no permitidos, múltiples fotogramas, atributos privados no admitidos, identificadores detectados, overlays y declaraciones de texto incrustado incompatibles. Estos filtros **no garantizan una desidentificación completa** ni conformidad general con DICOM. No se usa `force=True` para abrir cualquier contenido.

Una ecografía en DICOM o un objeto fuera del perfil se rechaza; una exportación PNG de esa ecografía puede visualizarse declarando la modalidad, pero su clasificación mamográfica queda bloqueada. Las imágenes coloreadas se convierten a luminancia solamente para el visor/laboratorio admitido, no para descubrir patología.

Informes: 10 MiB, 30.000 caracteres. PDF: hasta 12 páginas, sin cifrado, proceso separado, tiempo máximo 15 s y límites de recursos en Linux. No es una sandbox de seguridad certificada. Un documento malicioso podría explotar defectos de dependencias no descubiertos; se requiere análisis de seguridad del entorno de destino. DOCX: estructura ZIP acotada, XML sin entidades externas, cuerpo y tablas. No se ejecutan macros ni instrucciones del texto. TXT: UTF-8, UTF-16 con BOM o Windows-1252 explícitamente advertido.

No hay OCR automático, búsqueda en PACS, segmentación, fusión de vistas, reconocimiento automático de modalidad ni lectura clínica de fotografías externas.

## Sesión, almacenamiento y alojamiento

Las cargas se mantienen en memoria de la sesión y no se escriben de forma intencionada en archivos de casos. No existe base de datos de pacientes ni historial persistente. Las imágenes y los informes no se guardan con `st.cache_data`. Solo el recurso de modelo constante se comparte en caché; no contiene datos de sesiones.

Una aplicación alojada recibe archivos en su servidor. No es procesamiento exclusivo dentro del navegador. El proveedor puede mantener registros de infraestructura, memoria temporal o copias de seguridad según sus políticas. Borrar la sesión no es borrado forense, no elimina descargas y no controla los sistemas del proveedor.

La imagen y el informe deben pertenecer al mismo caso por verificación humana. Cargar imágenes inicia un caso nuevo. Cargar o editar un informe reinicia confirmaciones, señales y fechas para reducir arrastres de contexto. Debe comprobarse ese flujo con AppTest y en navegador en el destino: no fue ejecutado nativamente durante esta preparación.

El JSON y la guía PDF no incluyen el archivo fuente, nombres originales o el mapa del clasificador. Las fechas de consulta se exportan solo cuando el usuario descarga su guía. El evento ICS tiene texto genérico, sin BI-RADS ni diagnóstico, y no programa citas ni alarmas clínicas automáticas.

## Servicio de IA externa

Desactivado por defecto. Requiere Secrets y consentimiento para cada llamada. El payload contiene únicamente IDs y textos de explicaciones educativas de la base local. No envía pregunta libre, informe, imágenes, síntomas ni fechas. El conjunto de temas elegido puede permitir inferir qué contenido interesa al usuario: no equivale a una garantía de anonimato de metadatos.

Solo se aceptan IDs pertenecientes a los fragmentos que se enviaron. El texto libre de la respuesta nunca se muestra como consejo; una respuesta inválida deja vigente la base local. Se fija el host de la API, se impiden redirecciones y se usan límites de tiempo. No se muestran tokens ni mensajes completos del proveedor en errores.

`store=false` reduce persistencia de estado de la API, pero no elimina automáticamente registros de seguridad y abuso. La llamada real no fue probada. Fuente: documentación oficial de OpenAI, https://platform.openai.com/docs/models/default-usage-policies-by-endpoint.

## Riesgos residuales que requieren revisión

| Riesgo | Control incorporado | Pendiente |
|---|---|---|
| Falsa tranquilidad por una puntuación alta | Modelo fuera de la guía; advertencia de saturación | Validación de comprensión con usuarios |
| Informe de otra persona o de otra fecha | Caso nuevo, invalidación y confirmación manual | Identidad/correspondencia institucional, fuera de esta app |
| Varias categorías, lesiones o mamas | Todas las menciones visibles; no selección automática del máximo | Revisión radiológica; no omitir categorías relevantes |
| Dato faltante confundido con negativo | Respuesta «No sé» por defecto en casos propios | Usabilidad de las preguntas |
| Revelación de información sensible | Declaración, filtros y ausencia de historial de la app | Evaluación integral del alojamiento y desidentificación |
| Archivo malicioso o consumo de memoria | Límites, filtros de contenido, proceso PDF y errores controlados | Pentest, límites del servidor y revisión de dependencias |
| Recomendación inventada por IA externa | Respuesta limitada a IDs de contenido curado | Prueba con servicio real y revisión de los contenidos |
| Dependencias o interfaz incompatibles | Versiones declaradas, CI y AppTest proporcionados | Instalación limpia y aceptación nativa Streamlit |

No se realizó pentest, auditoría legal, certificación regulatoria, auditoría de vulnerabilidades en línea ni validación clínica.
