"""Genera solo ejemplos sintéticos. No crea etiquetas clínicas a partir de imágenes."""
from pathlib import Path
import sys,csv,json,zipfile
from io import BytesIO
from xml.sax.saxutils import escape
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from mammoapp.examples import CASES,scenario,image_bytes
from mammoapp.documents import read_report,confirm_category
from mammoapp.guidance import guide
from mammoapp.exports import _make_pdf,guide_pdf,technical_pdf
from mammoapp.images import load_image,image_statistics

def minimal_docx(text: str) -> bytes:
    body=(
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:body><w:p><w:r><w:t>'+escape(text)+'</w:t></w:r></w:p></w:body></w:document>'
    )
    b=BytesIO()
    with zipfile.ZipFile(b,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('word/document.xml',body)
    return b.getvalue()

def main():
    directory=ROOT/'examples';directory.mkdir(exist_ok=True)
    index=[]
    for code,c in CASES.items():
        (directory/f'{code}_FANTOMA.png').write_bytes(image_bytes(code,'PNG'))
        (directory/f'{code}_INFORME_FICTICIO.txt').write_text(c['report'],encoding='utf-8')
        case=scenario(code)
        category=confirm_category(c['report'],c['category'],True) if c['category'] else None
        result=guide(case['symptoms'],category)
        index.append({'case_id':code,'title':c['title'],'synthetic_only':True,'image_has_no_pathology_label':True,
                      'category_in_fictitious_report':c['category'],'symptoms':case['symptoms'],
                      'expected_educational_level':result.level,'lesson':c['lesson']})
    for fmt,ext in [('DICOM','dcm'),('TIFF','tiff'),('JPEG','jpg'),('BMP','bmp'),('WEBP','webp')]:
        (directory/f'ED03_FANTOMA.{ext}').write_bytes(image_bytes('ED03',fmt))
    (directory/'ED03_INFORME_FICTICIO.docx').write_bytes(minimal_docx(CASES['ED03']['report']))
    (directory/'ED03_INFORME_FICTICIO.pdf').write_bytes(_make_pdf('Informe radiológico ficticio','EJEMPLO ACADÉMICO: NO CORRESPONDE A UNA PERSONA.',[
        ('Texto para practicar la lectura',[CASES['ED03']['report']]),
        ('Propósito del archivo',['Se usa para probar la extracción de texto y la confirmación manual de BI-RADS. El fantoma no representa el hallazgo descrito.'])]))
    (directory/'escenarios_ficticios.json').write_text(json.dumps(index,ensure_ascii=False,indent=2),encoding='utf-8')
    c=scenario('ED04');r=guide(c['symptoms'],c['category'])
    (directory/'ED04_GUIA_EDUCATIVA_RESULTADO.pdf').write_bytes(guide_pdf(r,True))
    # Matriz de predicciones inventadas SOLO para enseñar cálculo, no salida del modelo.
    with (directory/'EJEMPLO_METRICAS_SINTETICAS.csv').open('w',newline='',encoding='utf-8') as f:
        fields=['image_id','patient_id','label','p_normal','p_benigno','p_maligno','label_source']
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        labels=['normal','benigno','maligno']
        for i in range(12):
            y=i%3;p=[.1,.1,.1];p[y]=.8
            if i in (2,6):p=[.1,.1,.1];p[(y+1)%3]=.8
            w.writerow({'image_id':f'SYN_I{i:03d}','patient_id':f'SYN_P{i:03d}','label':labels[y],
                        **dict(zip(['p_normal','p_benigno','p_maligno'],p)),'label_source':'synthetic_arithmetic_example_not_model_output'})
    print('Ejemplos sintéticos generados:',len(index),'escenarios.')
if __name__=='__main__':main()
