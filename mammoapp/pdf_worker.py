"""Proceso acotado para lectura textual de PDF; no OCR, no archivos temporales."""
import io, json, sys, logging

def main():
    try:
        try:
            import resource
            resource.setrlimit(resource.RLIMIT_AS,(768*1024*1024,768*1024*1024))
            resource.setrlimit(resource.RLIMIT_CPU,(10,10))
        except (ImportError,ValueError,OSError):
            pass  # En Windows rige el timeout del padre; no se afirma límite de memoria.
        logging.disable(logging.CRITICAL)
        from pypdf import PdfReader
        data=sys.stdin.buffer.read(10*1024*1024+1)
        if len(data)>10*1024*1024: raise ValueError()
        reader=PdfReader(io.BytesIO(data),strict=True)
        if reader.is_encrypted:
            print(json.dumps({'error':'El PDF está cifrado; use una copia textual autorizada.'}));return
        if len(reader.pages)>12: raise ValueError()
        chunks=[];blank=[]
        for i,page in enumerate(reader.pages):
            text=page.extract_text() or ''
            if not text.strip():blank.append(i+1)
            chunks.append(text)
            if sum(map(len,chunks))>30_000:raise ValueError()
        text='\n\n'.join(chunks)
        if not text.strip():
            print(json.dumps({'error':'El PDF no tiene texto extraíble. Puede ser un escaneo: transcriba y compruebe la conclusión; no se inventa una lectura.'}));return
        notes=[]
        if blank:notes.append('Hay páginas sin texto extraíble: '+', '.join(map(str,blank))+'. El texto puede estar incompleto; revise el original.')
        print(json.dumps({'text':text,'pages':len(reader.pages),'warnings':notes},ensure_ascii=True))
    except BaseException:
        print(json.dumps({'error':'PDF dañado o fuera de límites: máximo 12 páginas y 30.000 caracteres; requiere texto legible.'}))
if __name__=='__main__':main()
