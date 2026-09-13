from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
VERSION = "4.1.0"
IMAGE_EXT = ("dcm", "dicom", "png", "jpg", "jpeg", "tif", "tiff", "bmp", "webp")
REPORT_EXT = ("txt", "pdf", "docx")
MAX_IMAGE = 64 * 1024 * 1024
MAX_REPORT = 10 * 1024 * 1024
MAX_PIXELS = 32_000_000
MAX_DIM = 8192
MAX_TEXT = 30_000
DISCLAIMER = ("Aplicación académico-científica. No diagnostica cáncer, no certifica que sea seguro esperar "
              "y no sustituye la valoración profesional. Las alertas son orientaciones educativas, no un triaje validado.")
