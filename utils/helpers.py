import logging
from typing import List

from models import Chunk

logger = logging.getLogger(__name__)


def add_neighbor_info(chunks: List[Chunk]) -> List[Chunk]:
    """
    Dodaj referencje do poprzedniego i następnego chunka
    
    Args:
        chunks: Lista chunków bez informacji o sąsiedztwie
        
    Returns:
        Lista chunków z ustawionymi previous_chunk_id i next_chunk_id
    """
    try:
        for i, chunk in enumerate(chunks):
            if i > 0:
                chunk.previous_chunk_id = chunks[i - 1].id
            if i < len(chunks) - 1:
                chunk.next_chunk_id = chunks[i + 1].id
        
        logger.info(f"Dodano informacje o sąsiedztwie dla {len(chunks)} chunków")
        return chunks
    except Exception as e:
        logger.error(f"Błąd przy dodawaniu informacji o sąsiedztwie: {e}")
        raise


def validate_chunks(chunks: List[Chunk]) -> bool:
    """
    Waliduj listę chunków
    
    Args:
        chunks: Lista chunków do walidacji
        
    Returns:
        True jeśli wszystkie chunki są poprawne
    """
    if not chunks:
        logger.warning("Lista chunków jest pusta")
        return False
    
    for chunk in chunks:
        if not chunk.id or not chunk.content:
            logger.error(f"Chunk ma pusty ID lub content: {chunk}")
            return False
    
    logger.info(f"Walidacja {len(chunks)} chunków: OK")
    return True


def get_chunks_by_pdf(chunks: List[Chunk], pdf_name: str) -> List[Chunk]:
    """
    Filtruj chunki po nazwie PDF-a
    
    Args:
        chunks: Lista wszystkich chunków
        pdf_name: Nazwa PDF-a do filtrowania
        
    Returns:
        Gefiltrowani chunki
    """
    filtered = [c for c in chunks if c.pdf_name == pdf_name]
    logger.info(f"Gefiltrowani chunki z {pdf_name}: {len(filtered)}")
    return filtered


def get_chunks_by_page(chunks: List[Chunk], page_number: int) -> List[Chunk]:
    """
    Filtruj chunki po numerze strony
    
    Args:
        chunks: Lista wszystkich chunków
        page_number: Numer strony
        
    Returns:
        Gefiltrowani chunki
    """
    filtered = [c for c in chunks if c.page_number == page_number]
    logger.info(f"Gefiltrowani chunki ze strony {page_number}: {len(filtered)}")
    return filtered
