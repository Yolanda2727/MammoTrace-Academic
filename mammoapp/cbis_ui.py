"""Academic CBIS workspace; does not write uploaded files or modify case state."""
from pathlib import Path
import csv,io,json
import streamlit as st
import pandas as pd
from .config import ROOT
from .cbis import read_bundle,read_cases,FILENAMES,audit,partition,csv_bytes,image_inventory
from .cbis_dicom import read_cbis,preview
from mammotrace.errors import ResearchError

def cbis_page():
    st.subheader('CBIS-DDSM · Cohorte, procedencia y preparación científica')
    st.info('Referencia real de un conjunto público. Los CSV no son informes individuales ni convierten los pesos legados en un modelo entrenado con patología real.')
    try:
        uploads=st.file_uploader('Cargar los cuatro CSV oficiales de CBIS-DDSM',type=['csv'],accept_multiple_files=True,key='cbis_csvs')
        bundle=ROOT/'data/cbis'
        packaged=all((bundle/name).is_file() for name in FILENAMES)
        if uploads:
            if sorted(f.name for f in uploads)!=sorted(FILENAMES):st.warning('Cargue exactamente los cuatro archivos con sus nombres originales.');return
            rows=[r for f in uploads for r in read_cases(f.getvalue(),f.name)]
        elif packaged:
            rows=read_bundle(bundle)
        else:
            st.warning('La edición pública no redistribuye los CSV de terceros. Descárguelos desde la fuente CBIS-DDSM/TCIA y cárguelos aquí, o colóquelos en data/cbis/.')
            st.caption('Consulte data/cbis/README.md. No se inventan conteos ni etiquetas cuando los archivos fuente no están disponibles.')
            return
        a=audit(rows)
        c=st.columns(4)
        for col,title,value in zip(c,['Anotaciones lesión-vista','Sujetos únicos','Series de imagen completa','Sujetos train/test compartidos'],[a['annotation_rows'],a['subjects'],a['full_image_series'],len(a['overlap_subjects'])]):col.metric(title,value)
        st.dataframe(pd.DataFrame(a['source_counts']),hide_index=True,use_container_width=True)
        st.warning('BENIGN_WITHOUT_CALLBACK se conserva y solo puede agruparse como benigno para un objetivo binario explícito; no equivale a normal. No se calcula rendimiento diagnóstico.')
        st.write(f"{a['mixed_binary_image_groups']} imágenes contienen anotaciones con targets binarios diferentes; no se fuerza una etiqueta única. {a['mixed_binary_lesion_groups']} claves de lesión tienen discordancia entre vistas y requieren revisión.")
        with st.expander('Solapamientos y resultados verificables'):st.json(a)
        allow=st.checkbox('Aplicar holdout_priority: preservar test y excluir del entrenamiento los sujetos compartidos',key='cbis_split_confirm')
        if allow:
            parts=partition(rows,'holdout_priority');inv=image_inventory(parts)
            st.download_button('Descargar partición por sujeto (CSV)',csv_bytes(parts),'CBIS_particiones.csv','text/csv')
            st.download_button('Descargar inventario de imágenes elegibles (CSV)',csv_bytes(inv),'CBIS_inventario.csv','text/csv')
            st.caption('Validación determinista: 20% de sujetos train restantes; semilla 20260913. No es estratificada. No se entrena ni se evalúa automáticamente.')
        if not uploads and packaged:
            report=ROOT/'reports/cbis/cbis_audit.json'
            if report.exists():
                with st.expander('Manifiesto, digest y registro parcial de descarga'):st.json(json.loads(report.read_text()))
        st.markdown('#### Ejemplo real público: P_00038 · mama izquierda · CC')
        img=ROOT/'examples/cbis/P_00038_LEFT_CC_preview.png'
        if img.exists():st.image(str(img),caption='Vista derivada: reescalado y contraste percentil 1–99; no se han añadido lesiones ni mapas de IA.',width=380)
        st.caption('Fuente: Sawyer-Lee et al., CBIS-DDSM, TCIA, DOI 10.7937/K9/TCIA.2016.7O02S9CY; CC BY 3.0. No se ha creado un informe clínico narrativo para este archivo.')
        auth=st.checkbox('Cargar un DICOM público CBIS-DDSM autorizado y revisar privacidad',key='cbis_auth')
        if auth:
            f=st.file_uploader('DICOM CBIS de investigación (separado del caso personal)',type=['dcm','dicom'],key='cbis_dicom')
            if f:
                mapping={r[k+'_series_uid']:r['patient_id'] for r in rows for k in ('full','crop','mask')}
                im=read_cbis(f.getvalue(),mapping,authorized=True)
                st.image(preview(im),caption='Vista de investigación; no hay inferencia diagnóstica.',width=400)
                st.json(im.technical)
                for warning in im.warnings:st.caption(warning)
        st.code('python scripts/audit_cbis.py\npython scripts/index_cbis.py --root RUTA_DICOM --out reports/local_index.csv',language='bash')
    except ResearchError as exc:st.error(exc.message)
    except (OSError,ValueError,UnicodeError):st.error('No fue posible leer los recursos CBIS. Revise el registro y los archivos; no se sustituyen resultados.')
