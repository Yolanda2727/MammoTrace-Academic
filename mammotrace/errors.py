class ResearchError(ValueError):
    """Error público deliberado. No incluir valores DICOM ni nombres de archivo."""
    def __init__(self, code: str, message: str, status: int = 422):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status
