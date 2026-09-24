
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pdf_processing.chunker import get_processed_blocks, get_glued_str_only_blocks
import pdf_processing.chunker as chunker
import logging
#import sys
from pathlib import Path

from config import PDF_DIR, LOGS_DIR, LOG_LEVEL, OPENAI_API_KEY, LOG_FORMAT
from opensearch_integration.indexer import OpenSearchIndexer
from utils.helpers import add_neighbor_info, validate_chunks

# ============ KONFIGURACJA LOGGINGU ============
logging.basicConfig(
    level=LOG_LEVEL,
    format=LOG_FORMAT,
    handlers=[
        logging.FileHandler(LOGS_DIR / "processing.log"),
        logging.StreamHandler(sys.stdout)
    ]
) 
logger = logging.getLogger(__name__)


def main():
    """Główna funkcja orchestratora"""
    
    logger.info("=" * 60)
    logger.info("ROZPOCZĘCIE PRZETWARZANIA PDF-ÓW")
    logger.info("=" * 60)
    
    try:
        # Walidacja
        if not OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY nie ustawiony!")
        
        if not PDF_DIR.exists():
            logger.error(f"Katalog z PDF-ami nie istnieje: {PDF_DIR}")
            return
        
        # Inicjalizacja
        logger.info("Inicjalizacja komponentów...")
        #chunker = PDFChunker(api_key=OPENAI_API_KEY)
        #indexer = OpenSearchIndexer()
        
        # Utwórz indeks (force_recreate=True spowoduje usunięcie starego)
        #logger.info("Tworzenie/aktualizowanie indeksu OpenSearch...")
        #indexer.create_index(force_recreate=False)
        
        # Znajdź wszystkie PDF-y
        pdf_files = sorted(PDF_DIR.glob("*.pdf"))
        #pdf_files = sorted(PDF_DIR.glob("pdfs/*.pdf"))
        
        if not pdf_files:
            logger.warning(f"Brak plików PDF w {PDF_DIR}")
            return
        
        logger.info(f"Znaleziono {len(pdf_files)} plików PDF")
        
        # Przetwórz wszystkie PDF-y
        # all_chunks = []
        # for idx, pdf_file in enumerate(pdf_files, 1):
        #     try:
        #         logger.info(f"\n[{idx}/{len(pdf_files)}] Przetwarzanie: {pdf_file.name}")
        #         #chunks = chunker.process_pdf(str(pdf_file))
        #         #chunker = PDFChunker()
        #         #chunks = chunker.process_pdf_semantic(str(pdf_file))
        #         chunks = get_glued_str_only_blocks(get_processed_blocks(str(pdf_file)))
        #         all_chunks.extend(chunks)
        #         logger.info(f"Ukończono: {pdf_file.name} ({len(chunks)} chunków)")
        #     except Exception as e:
        #         logger.error(f"Błąd przy przetwarzaniu {pdf_file.name}: {e}")
        #         continue
        all_chunks = chunker.chunk_pdf_to_strings(map(str, pdf_files))
        
        # Walidacja
        # logger.info("\nWalidacja chunków...")
        # if not validate_chunks(all_chunks):
        #     logger.error("Walidacja chunków nie powiodła się!")
        #     return
        
        logger.info(f"Razem przetworzonych chunków: {len(all_chunks)}")
        
        # Dodaj informacje o sąsiedztwie
        # logger.info("Dodawanie informacji o sąsiedztwie...")
        # all_chunks = add_neighbor_info(all_chunks)
        with open("pdfs/chunks.txt", "w") as output_file:
            for chunked_pdf in all_chunks:
                output_file.write("#"*30)
                output_file.write("\n")
                output_file.write(chunked_pdf.path)
                output_file.write("\n")
                output_file.write("\n\n".join(chunked_pdf.chunks))
                output_file.write("\n")
        

        indexer = OpenSearchIndexer()
        for chunked_pdf in all_chunks:
            for chunk_index, single_chunk in enumerate(chunked_pdf.chunks):
                response = indexer.send_chunk(chunked_pdf.name, chunk_index, single_chunk)
                print(response)








    except Exception as e:
        logger.error(f"Krytyczny błąd: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

