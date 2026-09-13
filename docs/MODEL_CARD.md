# Model card · modelo legado original

## Identidad y procedencia

Archivo reconstruido: `models/modelo.h5`. Tamaño: **98.094.968 bytes**. SHA-256:

`0fae4daed4eaa93f05ea3e0c996181b463c21e464cab2a4e8fabef73f951977a`

Los pesos históricos pertenecen a una edición privada anterior y se conservaron sin reentrenar ni modificar durante la auditoría. Esta edición pública no redistribuye esos pesos y no infiere derechos sobre su procedencia o publicación.

Arquitectura inspeccionada durante la ejecución: ResNet50 con cabeza de tres clases, 179 capas y 23.850.371 parámetros. Entrada `224×224×3`, salida de tres puntuaciones softmax. Orden histórico: `normal`, `benigno`, `maligno`. Esos nombres se conservan únicamente como metadatos de integración.

## Problema de referencia y uso permitido

En `modelo_imagenes.py`, líneas 96–113 y 152–168, la etiqueta se deriva de banderas generadas al azar. En `actividad_3_1_imagenes.py` se repite ese procedimiento. Por lo tanto, el archivo no demuestra que las clases representen diagnósticos ni referencia histopatológica. La exactitud contra esas etiquetas no demuestra capacidad clínica.

Uso: comprobar carga, formato del tensor, consistencia de inferencia, sensibilidad a oclusiones y comunicación honesta de incertidumbre. No usar para decidir si hay cáncer, tranquilizar a una persona, priorizar su cita, indicar una biopsia o tratar síntomas.

## Preprocesamiento conservado

DICOM compatible → píxeles positivos → división por el máximo → redimensionamiento por área a 224×224 → repetición en tres canales → transformación ResNet: inversión del orden de canales y resta de medias `[103.939,116.779,123.68]`. La combinación de escala 0–1 y esas medias pertenece al flujo legado; no se corrige silenciosamente porque cambiaría la entrada esperada por sus pesos.

Para PNG/JPEG/TIFF/BMP/WebP se aplica luminancia y normalización por máximo como adaptación exploratoria. No se ha demostrado equivalencia con el DICOM ni robustez a compresión, fotografías de placas o cambios de contraste. La selección de modalidad es declarativa, no un detector automático.

La imagen del visor usa otro contraste para facilitar inspección. No es la entrada del modelo. MONOCHROME1 puede invertirse en la visualización, pero no se cambia silenciosamente el flujo legado. El visor no es una estación diagnóstica calibrada.

## Explicabilidad ejecutada

Método: oclusión, inspirado en la familia de perturbaciones estudiada por Zeiler y Fergus [1]. Se selecciona la clase histórica de mayor puntuación; se recupera su activación anterior al softmax y se ocultan 49 regiones de 32×32 del tensor. Cada región se sustituye por la mediana de la entrada. La diferencia firmada es:

`delta = logit_original − logit_con_region_oculta`.

La magnitud coloreada indica sensibilidad de esta activación. Un delta positivo significa que la oclusión redujo la activación. No establece la presencia ni la ubicación de una lesión, y no es una explicación causal de enfermedad. La matriz firmada queda en el JSON. El programa no presenta un mapa coloreado cuando la variación es numéricamente despreciable.

Se eligieron logits porque una salida softmax saturada puede ocultar cambios pequeños. Esto mejora la lectura numérica de la perturbación, pero no corrige etiquetas, sesgos, calibración ni validez clínica. `reports/model_probe.json` contiene la ejecución real sobre un fantoma, no una evaluación de pacientes.

## Qué falta antes de proponer un uso clínico

Referencia verificable; datos adecuados y representativos; separación por paciente; evaluación externa; calibración; análisis de falsos negativos; robustez por equipo, centro, densidad y subgrupos; evaluación de explicaciones; revisión independiente por especialistas; estudio de interacción humano-sistema y gobernanza institucional. Ninguno se presume resuelto por la auditoría técnica.

El entrenador heredado usa un flujo nuevo `standardized_v3` con preprocesamiento embebido. Sus modelos no sustituyen automáticamente el legado ni pueden cargarse desde el navegador: requieren integración y pruebas nuevas del adaptador.

[1] Zeiler MD, Fergus R. *Visualizing and Understanding Convolutional Networks*. ECCV 2014; arXiv:1311.2901. https://arxiv.org/abs/1311.2901
