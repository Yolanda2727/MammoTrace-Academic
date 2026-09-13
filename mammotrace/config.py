from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
import os
import secrets

ROOT = Path(__file__).resolve().parents[1]
WARNING = ("Uso exclusivo de investigación y formación. No es un diagnóstico, "
           "no estima riesgo individual de cáncer y no debe orientar decisiones clínicas.")
CLASSES = ("normal", "benigno", "maligno")

@dataclass(frozen=True)
class Settings:
    token: str = field(default_factory=lambda: os.environ.get("MAMMO_TOKEN") or secrets.token_urlsafe(32))
    model_dir: Path = field(default_factory=lambda: Path(os.environ.get("MAMMO_MODEL_DIR", str(ROOT / "models"))).resolve())
    backend: str = field(default_factory=lambda: os.environ.get("MAMMO_BACKEND", "torch"))
    max_upload_bytes: int = 64 * 1024 * 1024
    max_pixels: int = 32_000_000
    max_dimension: int = 8192
    max_csv_bytes: int = 4 * 1024 * 1024
    max_csv_rows: int = 10000
    max_requests_per_minute: int = 60
    testing: bool = False
    load_model: bool = True
    allow_remote: bool = False

    def __post_init__(self):
        if len(self.token) < 32:
            raise ValueError("La clave de sesión debe tener al menos 32 caracteres.")
        if self.backend not in {"torch", "tensorflow"}:
            raise ValueError("Motor permitido: torch o tensorflow.")
        if self.max_upload_bytes <= 0 or self.max_pixels <= 0:
            raise ValueError("Los límites deben ser positivos.")
