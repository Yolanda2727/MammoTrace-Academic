# Uso académico y trayectoria de investigación

## Ocho escenarios, tres fuentes de afirmaciones

El ejercicio diferencia **imagen**, **informe** y **síntomas declarados**. Las imágenes son fantomas geométricos; no se debe atribuir a un fantoma la categoría del informe ficticio que lo acompaña. Esa asociación existe para ensayar el flujo de interacción, no para crear un conjunto de entrenamiento.

ED01 trabaja la evaluación incompleta; ED02, la vigilancia; ED03, la diferencia entre sospecha y confirmación; ED04, la señal nueva frente a un informe benigno; ED05, inflamación y fiebre; ED06, deterioro importante; ED07, la distinción entre previo y actual; ED08, información no disponible.

Preguntas para la clase: ¿de dónde proviene cada afirmación?, ¿qué verifica el programa y qué solo declara el usuario?, ¿cuándo una explicación atractiva aumenta indebidamente la confianza?, ¿qué dato necesita el profesional para decidir?

Buenas prácticas: confirmar texto, conservar incertidumbre, no reutilizar contextos de otras personas, revisar errores y citar las fuentes. Malas prácticas: inventar etiquetas, interpretar una imagen cualquiera como mamografía, llamar diagnóstico a la mayor puntuación, comunicar que es seguro esperar o usar precisión global para ocultar falsos negativos.

Falacias a discutir: sesgo de automatización, autoridad del mapa de calor, equivalencia entre probabilidad softmax y riesgo, confusión entre rendimiento técnico y utilidad clínica, y suposición de que una categoría benigna elimina toda señal nueva.

## Evaluación de un CSV aportado

Formato mínimo:

```csv
patient_id,label,p_normal,p_benigno,p_maligno
P001,normal,0.80,0.10,0.10
```

La fila anterior es ilustrativa, no resultado del modelo. `image_id` único es recomendado. Las clases admitidas son `normal`, `benigno`, `maligno`; las tres puntuaciones deben ser finitas, estar entre 0 y 1 y sumar 1. Máximo 10.000 filas. El validador comprueba estructura, no verifica diagnósticos, independencia del entrenamiento ni autorización.

```bash
python scripts/evaluate.py examples/EJEMPLO_METRICAS_SINTETICAS.csv --bootstrap 300
```

Ese archivo tiene etiquetas y puntuaciones artificiales exclusivamente para enseñar aritmética. Sus métricas no se deben incluir como resultados de desempeño del clasificador ni de pacientes. El módulo calcula matriz de confusión, sensibilidad, especificidad, precisión, F1, AUC, Brier y log-loss. Los intervalos por percentiles se calculan remuestreando pacientes completos para accuracy, F1 macro y sensibilidad de la clase maligna. No todas las métricas reciben intervalos. Si falta un denominador se informa que no es estimable; con menos de cinco pacientes no se calculan intervalos.

## Entrenador de investigación heredado

`training/train.py` conserva la separación por paciente antes del balanceo, los pesos de clase y un flujo finito de validación/prueba. Exige referencia declarada y verificada por el operador. Formato del CSV:

```csv
dicom_path,label,patient_id,label_source,label_verified
caso001/imagen.dcm,benigno,P001,reference_documented,true
```

La fila es solo una plantilla. No genere etiquetas por azar ni por el nombre del archivo. El validador exige que el tamaño del conjunto permita los grupos y detecta duplicados/rutas no autorizadas. La marca `true` es una declaración humana, no una comprobación de la histopatología.

```bash
python -m training.train --labels data/labels.csv --data-root data --output training_runs/run_001 --authorized-data --backend torch --weights imagenet --epochs-head 8 --epochs-finetune 12
```

`--weights imagenet` descarga pesos externos explícitamente. Sin esa opción el entrenador inicia sin pesos ImageNet. El entrenamiento no se lanza desde la interfaz pública. El archivo de salida usa `standardized_v3`, distinto del flujo legado; no lo copie encima del modelo de esta aplicación. La adaptación para otro modelo requiere nuevas pruebas y una model card nueva.

**En esta versión no se repitió un entrenamiento completo ni se incorporaron pacientes.** Se conservó el entrenador de la entrega anterior; se reejecutaron los controles de datos y evaluación. La prueba de modelo de esta entrega es inferencia y oclusión, no aprendizaje ni validación clínica.

## Estudios necesarios

Primero: revisión de reglas y lenguaje por especialistas, evaluación de privacidad y autorización ética correspondiente. Después: estudio de usabilidad con escenarios ficticios y evaluación de comprensión/automatización. Para estudiar un clasificador clínico se requiere referencia trazable, cohortes independientes, evaluación de calibración, análisis por subgrupos y centro, revisión de falsos negativos y robustez de los mapas.

Para la guía, analizar falsas tranquilizaciones, sensibilidad a datos ausentes, errores de transcripción, interpretación de categorías múltiples y seguimiento del plan profesional. Ninguna prueba de software reemplaza estas evaluaciones.
