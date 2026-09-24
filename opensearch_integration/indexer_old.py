import logging
from typing import List, Dict, Any

from opensearchpy import OpenSearch, NotFoundError

from config import (
    OPENSEARCH_HOST,
    OPENSEARCH_PORT,
    OPENSEARCH_USER,
    OPENSEARCH_PASSWORD,
    OPENSEARCH_INDEX,
    OPENSEARCH_USE_SSL,
    OPENSEARCH_VERIFY_CERTS
)
from models import Chunk

logger = logging.getLogger(__name__)


class OpenSearchIndexer:
    """Klasa do zarządzania indeksem OpenSearch i wgrywaniem chunków"""
    
    def __init__(
        self,
        host: str = OPENSEARCH_HOST,
        port: int = OPENSEARCH_PORT,
        username: str = OPENSEARCH_USER,
        password: str = OPENSEARCH_PASSWORD,
        index_name: str = OPENSEARCH_INDEX
    ):
        """
        Inicjalizacja OpenSearchIndexer
        
        Args:
            host: Host OpenSearch
            port: Port OpenSearch
            username: Nazwa użytkownika
            password: Hasło
            index_name: Nazwa indeksu
        """
        try:
            self.client = OpenSearch(
                hosts=[{'host': host, 'port': port}],
                http_auth=(username, password),
                use_ssl=OPENSEARCH_USE_SSL,
                verify_certs=OPENSEARCH_VERIFY_CERTS,
                ssl_show_warn=False
            )
            self.index_name = index_name
            logger.info(f"Połączono z OpenSearch: {host}:{port}")
        except Exception as e:
            logger.error(f"Błąd połączenia z OpenSearch: {e}")
            raise
    
    def create_index(self, force_recreate: bool = False):
        """
        Utwórz indeks z odpowiednią mapą
        
        Args:
            force_recreate: Jeśli True, usuń istniejący indeks i utwórz nowy
        """
        index_body = {
            "settings": {
                "index": {
                    "number_of_shards": 2,
                    "number_of_replicas": 0,
                    "analysis": {
                        "analyzer": {
                            "standard_analyzer": {
                                "type": "standard",
                                "stopwords": "_english_"
                            }
                        }
                    }
                }
            },
            "mappings": {
                "properties": {
                    "id": {
                        "type": "keyword"
                    },
                    "pdf_name": {
                        "type": "keyword"
                    },
                    "page_number": {
                        "type": "integer"
                    },
                    "chunk_index": {
                        "type": "integer"
                    },
                    "content": {
                        "type": "text",
                        "analyzer": "standard_analyzer",
                        "fields": {
                            "keyword": {
                                "type": "keyword",
                                "ignore_above": 256
                            }
                        }
                    },
                    "previous_chunk_id": {
                        "type": "keyword"
                    },
                    "next_chunk_id": {
                        "type": "keyword"
                    },
                    "created_at": {
                        "type": "date"
                    },
                    "status": {
                        "type": "keyword"
                    }
                }
            }
        }
        
        try:
            # Sprawdź czy indeks istnieje
            exists = self.client.indices.exists(index=self.index_name)
            
            if exists and force_recreate:
                logger.info(f"Usuwanie istniejącego indeksu '{self.index_name}'")
                self.client.indices.delete(index=self.index_name)
            
            if not exists or force_recreate:
                logger.info(f"Tworzenie indeksu '{self.index_name}'")
                self.client.indices.create(index=self.index_name, body=index_body)
                logger.info(f"Indeks '{self.index_name}' został utworzony")
            else:
                logger.info(f"Indeks '{self.index_name}' już istnieje")
                
        except Exception as e:
            logger.error(f"Błąd przy tworzeniu indeksu: {e}")
            raise
    
    def index_chunks(self, chunks: List[Chunk], batch_size: int = 100):
        """
        Wgraj chunki do OpenSearch
        
        Args:
            chunks: Lista chunków do wgrania
            batch_size: Rozmiar batcha do bulk operacji
        """
        if not chunks:
            logger.warning("Brak chunków do wgrania")
            return
        
        logger.info(f"Wgrywanie {len(chunks)} chunków do OpenSearch...")
        
        try:
            for i, chunk in enumerate(chunks):
                try:
                    self.client.index(
                        index=self.index_name,
                        id=chunk.id,
                        body=chunk.dict()
                    )
                    
                    if (i + 1) % batch_size == 0:
                        logger.info(f"  Wgrano {i + 1}/{len(chunks)} chunków")
                except Exception as e:
                    logger.error(f"Błąd przy wgrywaniu chunka {chunk.id}: {e}")
                    continue
            
            logger.info(f"Wgrywanie ukończone! Wgrano {len(chunks)} chunków")
            
        except Exception as e:
            logger.error(f"Błąd przy wgrywaniu chunków: {e}")
            raise
    
    def search_chunks(self, query: str, size: int = 10) -> List[Dict[str, Any]]:
        """
        Wyszukaj chunki
        
        Args:
            query: Tekst zapytania
            size: Liczba wyników
            
        Returns:
            Lista znalezionych chunków
        """
        search_body = {
            "size": size,
            "query": {
                "multi_match": {
                    "query": query,
                    "fields": ["content", "content.keyword"]
                }
            }
        }
        
        try:
            results = self.client.search(index=self.index_name, body=search_body)
            logger.info(f"Wyszukiwanie '{query}': znaleziono {len(results['hits']['hits'])} wyników")
            return results["hits"]["hits"]
        except Exception as e:
            logger.error(f"Błąd przy wyszukiwaniu: {e}")
            return []
    
    def get_chunk_with_neighbors(self, chunk_id: str) -> Dict[str, Any]:
        """
        Pobierz chunk razem z jego sąsiadami (poprzedni i następny)
        
        Args:
            chunk_id: ID chunka
            
        Returns:
            Słownik z kluczami: current, previous (opcjonalny), next (opcjonalny)
        """
        try:
            chunk_doc = self.client.get(index=self.index_name, id=chunk_id)
            chunk_data = chunk_doc["_source"]
            
            result = {"current": chunk_data}
            
            # Pobierz poprzedni chunk
            if chunk_data.get("previous_chunk_id"):
                try:
                    prev_doc = self.client.get(
                        index=self.index_name,
                        id=chunk_data["previous_chunk_id"]
                    )
                    result["previous"] = prev_doc["_source"]
                except NotFoundError:
                    logger.warning(f"Poprzedni chunk nie znaleziony: {chunk_data['previous_chunk_id']}")
            
            # Pobierz następny chunk
            if chunk_data.get("next_chunk_id"):
                try:
                    next_doc = self.client.get(
                        index=self.index_name,
                        id=chunk_data["next_chunk_id"]
                    )
                    result["next"] = next_doc["_source"]
                except NotFoundError:
                    logger.warning(f"Następny chunk nie znaleziony: {chunk_data['next_chunk_id']}")
            
            return result
            
        except NotFoundError:
            logger.error(f"Chunk nie znaleziony: {chunk_id}")
            raise
        except Exception as e:
            logger.error(f"Błąd przy pobieraniu chunka z sąsiadami: {e}")
            raise
    
    def delete_chunks_by_pdf(self, pdf_name: str) -> int:
        """
        Usuń wszystkie chunki pochodzące z danego PDF-a
        
        Args:
            pdf_name: Nazwa PDF-a
            
        Returns:
            Liczba usuniętych chunków
        """
        try:
            query_body = {
                "query": {
                    "term": {
                        "pdf_name.keyword": pdf_name
                    }
                }
            }
            
            result = self.client.delete_by_query(index=self.index_name, body=query_body)
            deleted_count = result["deleted"]
            logger.info(f"Usunięto {deleted_count} chunków z PDF-a: {pdf_name}")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Błąd przy usuwaniu chunków: {e}")
            raise
    
    def get_index_stats(self) -> Dict[str, Any]:
        """
        Pobierz statystyki indeksu
        
        Returns:
            Słownik ze statystykami
        """
        try:
            stats = self.client.indices.stats(index=self.index_name)
            docs_count = stats["indices"][self.index_name]["primaries"]["docs"]["count"]
            size_in_bytes = stats["indices"][self.index_name]["primaries"]["store"]["size_in_bytes"]
            
            return {
                "index_name": self.index_name,
                "total_documents": docs_count,
                "size_in_bytes": size_in_bytes,
                "size_in_mb": size_in_bytes / (1024 * 1024)
            }
        except Exception as e:
            logger.error(f"Błąd przy pobieraniu statystyk: {e}")
            raise
