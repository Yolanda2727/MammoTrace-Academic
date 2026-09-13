"""Lectura acotada de informes. Nunca asigna un BI-RADS a partir de la imagen."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from io import BytesIO
import json
import re
import subprocess
import sys
import zipfile
from defusedxml import ElementTree
from mammotrace.errors import ResearchError
from .config import MAX_REPORT, MAX_TEXT

@dataclass(frozen=True)
class ReportDocument:
    text: str
    format: str
    pages: int | None
    warnings: tuple[str,...] = ()

BIRADS_RE = re.compile(
    r"\b(?:BI[\s\-‐‑–_]*RADS|BR)\s*(?:categor[ií]a\s*)?[:=\-]?\s*"
    r"([0-6])(?:[ \t]*([ABCabc])(?=\W|$))?(?![\w]|[ \t]*\d)", re.I)
CATS = ("0","1","2","3","4","4A","4B","4C","5","6")


def clean_text(text: str) -> str:
    if not isinstance(text,str) or len(text)>MAX_TEXT:
        raise ResearchError("TEXT_LIMIT", "El informe supera 30.000 caracteres o no es texto válido.")
    text=text.replace("\r\n","\n").replace("\r","\n")
    text="".join(c for c in text if c in "\n\t" or ord(c)>=32)
    if not text.strip():
        raise ResearchError("NO_TEXT", "No se encontró texto legible. Transcriba el informe y compruébelo con el original.")
    return text.strip()


def read_report(data: bytes, filename: str) -> ReportDocument:
    if not isinstance(data,bytes) or not data or len(data)>MAX_REPORT:
        raise ResearchError("REPORT_SIZE", "Informe vacío o mayor de 10 MiB.")
    ext=Path(filename).suffix.lower()
    notes=[]; pages=None
    try:
        if ext==".txt":
            if b"\x00" in data[:100] and not data.startswith((b"\xff\xfe",b"\xfe\xff")):
                raise ResearchError("TEXT_BINARY","El TXT parece contener datos binarios.")
            if data.startswith((b"\xff\xfe",b"\xfe\xff")):
                text=data.decode("utf-16")
            else:
                try: text=data.decode("utf-8-sig")
                except UnicodeDecodeError:
                    text=data.decode("cp1252")
                    notes.append("TXT decodificado como Windows-1252; confirme tildes y signos.")
        elif ext==".docx":
            with zipfile.ZipFile(BytesIO(data)) as z:
                infos=z.infolist()
                if len(infos)>1000 or sum(x.file_size for x in infos)>20*1024*1024:
                    raise ResearchError("DOCX_LIMIT","DOCX excesivamente grande al descomprimir.")
                if any(x.flag_bits & 1 or x.filename.startswith('/') or '..' in x.filename.split('/') for x in infos):
                    raise ResearchError("DOCX_STRUCTURE","DOCX cifrado o estructura no admitida.")
                if "word/document.xml" not in z.namelist() or z.getinfo("word/document.xml").file_size>2*1024*1024:
                    raise ResearchError("DOCX_STRUCTURE","No se encontró un cuerpo DOCX válido dentro del límite.")
                root=ElementTree.fromstring(z.read("word/document.xml"))
                ns={"w":"http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
                lines=[]
                for p in root.findall('.//w:p',ns):
                    lines.append(''.join(t.text or '' for t in p.findall('.//w:t',ns)))
                text='\n'.join(lines)
                if any(x.filename.startswith(('word/header','word/footer','word/footnotes','word/comments')) for x in infos):
                    notes.append("Se lee el cuerpo y sus tablas; encabezados, notas, comentarios e imágenes no se usan como evidencia. Confirme que la conclusión esté completa.")
        elif ext==".pdf":
            if not data.startswith(b"%PDF-"):
                raise ResearchError("PDF_SIGNATURE","La extensión PDF no coincide con su contenido.")
            # Aislamiento en otro proceso: sin temporales ni texto clínico en la línea de comandos.
            completed=subprocess.run([sys.executable,"-m","mammoapp.pdf_worker"],input=data,
                                     capture_output=True,timeout=15,check=False,cwd=str(Path(__file__).resolve().parents[1]))
            if completed.returncode!=0 or len(completed.stdout)>200_000:
                raise ResearchError("PDF_READ","PDF no legible, cifrado o fuera de los límites de recursos.")
            payload=json.loads(completed.stdout)
            if payload.get("error"):
                raise ResearchError("PDF_READ",payload["error"])
            text=payload["text"]; pages=payload["pages"]; notes+=payload.get("warnings",[])
        else:
            raise ResearchError("REPORT_EXT","Use TXT, PDF con texto o DOCX. Un PDF escaneado requiere transcripción comprobada.")
    except ResearchError:
        raise
    except subprocess.TimeoutExpired:
        raise ResearchError("PDF_TIMEOUT","La lectura del PDF excedió 15 segundos. Use una copia textual o transcriba el informe.") from None
    except Exception:
        raise ResearchError("REPORT_DECODE","No se pudo leer el informe en el formato declarado.") from None
    text=clean_text(text)
    if re.search(r"(?:paciente|nombre|identificaci[oó]n|c[eé]dula|tel[eé]fono|email)\s*:\s*\S",text,re.I):
        notes.append("Hay campos que podrían identificar a una persona. No comparta ni exporte el informe sin revisar su desidentificación.")
    return ReportDocument(text,ext[1:].upper(),pages,tuple(notes))


def extract_birads(text: str) -> list[dict]:
    """Devuelve TODAS las menciones con sus fragmentos. No selecciona la mayor ni la última."""
    text=clean_text(text)
    result=[]
    for m in BIRADS_RE.finditer(text):
        category=m.group(1)+(m.group(2) or '').upper()
        if category not in CATS: continue
        line_start=max(text.rfind('\n',0,m.start()),text.rfind('.',0,m.start()),text.rfind(';',0,m.start()))+1
        line_end=text.find('\n',m.end())
        if line_end<0: line_end=len(text)
        snippet=text[max(line_start,m.start()-100):min(line_end,m.end()+130)]
        before=text[max(line_start,m.start()-50):m.start()].lower()
        historical=bool(re.search(r"previo|anterior|antecedente|hist[oó]rico",before))
        negated=bool(re.search(r"\b(?:no es|descart(?:a|ado)|no corresponde a|no se asigna|sin criterios para|no hay hallazgos|no se observan|se descarta)(?:\s+la\s+categor[ií]a)?\s*$",before))
        result.append({"category":category,"start":m.start(),"end":m.end(),"evidence":snippet,
                       "historical_hint":historical,"negated_hint":negated,
                       "requires_human_confirmation":True})
    return result


def confirm_category(text: str, selection: str | None, reviewed: bool) -> str | None:
    """La confirmación debe referirse a una mención existente, no a una predicción."""
    if not selection or not reviewed:
        return None
    matches=extract_birads(text)
    if selection not in CATS or not any(m['category']==selection and not m['negated_hint'] and not m['historical_hint'] for m in matches):
        raise ResearchError("BIRADS_CONFIRM", "La categoría no aparece como mención utilizable en el informe. Revise o transcriba el texto exacto.")
    return selection
