# Aceptación nativa de Streamlit — pendiente en esta entrega

Estas comprobaciones se deben realizar donde Streamlit se instale realmente. Durante la preparación no se pudo descargar la dependencia por un fallo de resolución DNS. El archivo Python compiló, pero **compilar no prueba widgets, sesiones ni navegador**.

## Comandos

```bash
python -m pip install -r requirements-dev.txt
python scripts/check_environment.py
python -m pytest tests -q
python -m pytest tests_streamlit -q
python -m streamlit run streamlit_app.py
```

Registre fecha, sistema, Python, Streamlit, commit y versión del manifiesto de pesos. El workflow de GitHub Actions ejecuta ambos grupos de pruebas; debe conservarse su resultado real, no asumir que ya pasó por existir el YAML.

## Recorrido manual mínimo

| Comprobación | Resultado esperado | Estado de preparación |
|---|---|---|
| Abrir sin datos | Sin excepciones; sin modelo cargado automáticamente; sin categoría confirmada | Pendiente |
| Cargar los ocho ejemplos | Fantoma e informe ficticios visibles; no asignación automática de categoría | Pendiente |
| Confirmar ED03 | Solo tras seleccionar 4A y confirmar el texto se usa en la guía | Pendiente |
| Editar el informe | Se invalida la confirmación y se reinician señales/fechas | Pendiente |
| Cargar nueva imagen | No se conservan informe o síntomas del caso anterior | Pendiente |
| ED04 con informe 2 y bulto nuevo | Se mantiene la recomendación de contactar al equipo | Pendiente |
| ED06 con deterioro | Orientación urgente sin esperar el modelo | Pendiente |
| Fotografía o ecografía | Visor disponible en formato compatible; clasificador bloqueado | Pendiente |
| PDF escaneado o cifrado | Error comprensible/transcripción; no lectura inventada | Pendiente |
| DICOM incompatible | Rechazo sin traza, identificadores ni salida aleatoria | Pendiente |
| Modelo completo y oclusión | 49 celdas; límites visibles; nada se transfiere a la guía | Pendiente |
| Edición sin pesos | Informa ausencia; no inventa inferencia | Pendiente |
| Descargas PDF/JSON/ICS | Archivo abre; sin nombre de archivo clínico ni puntuaciones en la guía | Pendiente |
| Dos navegadores/sesiones | Imágenes, texto, señales y fechas no se mezclan | Pendiente |
| Limpiar sesión | Se vacían datos, confirmaciones, resultados y cargadores | Pendiente |
| Pantalla pequeña/lector asistivo | Contenido, controles y advertencias accesibles | Pendiente |
| Sin API externa | Asistente local disponible, cero llamadas externas de explicación | Pendiente |
| API externa habilitada | Solo payload público aprobado; IDs limitados; error seguro ante fallo | Pendiente de prueba real |
| Repositorio y app privados | Acceso denegado a usuarios no autorizados según configuración | Pendiente |

No se debe anunciar el despliegue como operativo hasta completar el recorrido. No abrir una demostración a pacientes reales como si fuera una herramienta asistencial. Los resultados de AppTest no sustituyen navegador, prueba de accesibilidad, carga ni seguridad del alojamiento.
