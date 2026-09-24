from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum
from typing import List
from pydantic import BaseModel, Field



class ChunkStatus(str, Enum):
    """Status przetwarzania chunka"""
    PENDING = "pending"
    PROCESSED = "processed"
    FAILED = "failed"


class Chunk(BaseModel):
    """Model pojedynczego chunka (paragrafu)"""
    
    id: str = Field(..., description="Unikatowy identyfikator: {pdf_name}_{page}_{chunk_index}")
    pdf_name: str = Field(..., description="Nazwa oryginalnego pliku PDF")
    page_number: int = Field(..., description="Numer strony w dokumencie")
    chunk_index: int = Field(..., description="Indeks paragrafu na stronie")
    content: str = Field(..., description="Treść paragrafu")
    
    # Metadane sąsiedztwa
    previous_chunk_id: Optional[str] = Field(None, description="ID poprzedniego chunka")
    next_chunk_id: Optional[str] = Field(None, description="ID następnego chunka")
    
    # Metadane dokumentu
    created_at: datetime = Field(default_factory=datetime.now, description="Data utworzenia")
    status: ChunkStatus = Field(default=ChunkStatus.PROCESSED, description="Status przetwarzania")
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "report_1_0",
                "pdf_name": "report.pdf",
                "page_number": 1,
                "chunk_index": 0,
                "content": "To jest akapit z dokumentu...",
                "previous_chunk_id": None,
                "next_chunk_id": "report_1_1",
                "created_at": "2025-11-27T19:30:00",
                "status": "processed"
            }
        }

    def dict(self, **kwargs):
        """Override dict() aby konwertować datetime na string"""
        data = super().dict(**kwargs)
        data['created_at'] = self.created_at.isoformat()
        return data


class DocumentMetadata(BaseModel):
    """Metadane dokumentu"""
    pdf_name: str
    total_pages: int
    total_chunks: int
    processed_at: datetime = Field(default_factory=datetime.now)
    chunks_per_page: dict[int, int] = Field(default_factory=dict)


class ParagraphsResponse(BaseModel):
    """Odpowiedź z GPT: lista akapitów jako stringi"""
    paragraphs: List[str] = Field(
        default_factory=list,
        description="Lista akapitów; każdy element musi być pojedynczym stringiem",
    )

class OCRResponse(BaseModel):
    """Odpowiedź OCR z GPT: lista tekstu"""
    text: List[str] = Field(
        default_factory=list,
        description="Lista akapitów z OCR"
    )
