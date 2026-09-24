'''import base64
import json
import logging
import re
from typing import List, Tuple
from pathlib import Path
from io import BytesIO

from pdf2image import convert_from_path
from openai import OpenAI
from langchain_text_splitters import RecursiveCharacterTextSplitter

from config import OPENAI_API_KEY, OPENAI_MODEL, OPENAI_MAX_TOKENS
from models import Chunk
from models import Chunk, ParagraphsResponse
from langchain.embeddings import OpenAIEmbeddings
from langchain_text_splitters import SemanticChunker



logger = logging.getLogger(__name__)


class PDFChunker:
    """Klasa do przetwarzania PDF-ów i dzielenia ich na chunki za pomocą GPT-4o + LangChain overlap"""

    def __init__(self, api_key: str = OPENAI_API_KEY):
        """
        Inicjalizacja PDFChunker

        Args:
            api_key: Klucz API OpenAI
        """
        self.client = OpenAI(api_key=api_key)
        self.model = OPENAI_MODEL
        logger.info(f"PDFChunker zainicjalizowany z modelem {self.model}")

    def pdf_to_images(self, pdf_path: str) -> List[Tuple[int, any]]:
        """
        Konwertuj PDF na listę obrazów

        Args:
            pdf_path: Ścieżka do pliku PDF

        Returns:
            Lista krotek (numer_strony, obraz_PIL)
        """
        try:
            logger.info(f"Konwertowanie PDF na obrazy: {pdf_path}")
            images = convert_from_path(pdf_path)
            return [(i + 1, img) for i, img in enumerate(images)]
        except Exception as e:
            logger.error(f"Błąd przy konwersji PDF na obrazy: {e}")
            raise

    def image_to_base64(self, image) -> str:
        """
        Konwertuj obraz PIL do base64

        Args:
            image: Obraz PIL

        Returns:
            String base64
        """
        try:
            buffered = BytesIO()
            image.save(buffered, format="PNG")
            return base64.b64encode(buffered.getvalue()).decode("utf-8")
        except Exception as e:
            logger.error(f"Błąd przy konwersji obrazu do base64: {e}")
            raise

    def chunk_page_with_gpt(
        self, image_base64: str, page_number: int, pdf_name: str
    ) -> List[str]:
        """
        Użyj GPT-4o do chunking'u strony PDF

        Args:
            image_base64: Obraz strony w base64
            page_number: Numer strony
            pdf_name: Nazwa PDF-a (dla logów)

        Returns:
            Lista akapitów (chunków)
        """

        prompt = """
Przepisz dokładnie tekst z tej strony PDF i podziel go na spójne akapity.

Wymagania:
1. Każdy akapit powinien być samowystarczalnym fragmentem tekstu.
2. Zachowaj oryginalną strukturę: nagłówki, podpunkty, numerację, itp.
3. Zwróć odpowiedź w formacie JSON z kluczem "paragraphs" zawierającym listę akapitów.
4. NIE streszczaj tekstu, NIE pomijaj fragmentów – każdy fragment tekstu widoczny na stronie ma trafić do któregoś akapitu.
5. Jeśli strona jest pusta lub zawiera tylko obrazy bez tekstu, zwróć pustą listę.

Przykład formatu:
"paragraphs": [
  "Pierwszy akapit...",
  "Drugi akapit...",
  "Trzeci akapit..."
]

WAŻNE: Zwróć WYŁĄCZNIE JSON, bez dodatkowego tekstu ani markdown'u.
""".strip()

        try:
            logger.debug(f"Wysyłanie strony {page_number} do GPT-4o")

            message = self.client.chat.completions.create(
                model=self.model,  # np. "gpt-4o"
                max_tokens=OPENAI_MAX_TOKENS,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{image_base64}",
                                },
                            },
                            {
                                "type": "text",
                                "text": prompt,
                            },
                        ],
                    }
                ],
            )

            # content może być listą części – zamieniamy na string
            content_parts = message.choices[0].message.content
            if isinstance(content_parts, list):
                response_text = "".join(
                    getattr(part, "text", "")
                    for part in content_parts
                    if getattr(part, "type", None) == "text"
                )
            else:
                response_text = str(content_parts)
            
            logger.setLevel("DEBUG")
            # Usuwanie ewentualnych ```...``` z odpowiedzi
            if "```json" in response_text:
                response_text = response_text.split("```json", 1)[1].split("```", 1)[0]
            elif "```" in response_text:
                parts = response_text.split("```")
                if len(parts) >= 3:
                    response_text = parts[1]
                else:
                    response_text = parts[-1]

            response_text = response_text.strip()

            data = json.loads(response_text)
            validated = ParagraphsResponse(**data)
            paragraphs = validated.paragraphs


            logger.info(f"Strona {page_number} ({pdf_name}): {len(paragraphs)} akapitów")

            for i in range(min(3, len(paragraphs))):
                logger.debug(f" Akapit {i+1}: {paragraphs[i][:100]}...")

            return paragraphs

        except json.JSONDecodeError as e:
            logger.error(
                f"Błąd parsowania JSON z GPT-4o na stronie {page_number}: {e}"
            )
            return []
        except Exception as e:
            logger.error(f"Błąd komunikacji z GPT-4o na stronie {page_number}: {e}")
            raise

    def process_pdf(self, pdf_path: str) -> List[Chunk]:
        """
        Przetwórz cały PDF i zwróć listę chunków z LangChain overlap

        Args:
            pdf_path: Ścieżka do pliku PDF

        Returns:
            Lista obiektów Chunk
        """
        pdf_name = Path(pdf_path).name
        all_chunks: List[Chunk] = []

        try:
            # PDF na obrazy
            logger.info(f"Przetwarzanie PDF: {pdf_name}")
            images = self.pdf_to_images(pdf_path)
            logger.info(f"Konwertowano na {len(images)} stron")

            # GPT-4o na każdej stronie jako wstępne akapity
            for page_number, image in images:
                try:
                    logger.info(
                        f" Chunking strona {page_number}/{len(images)} (GPT)"
                    )
                    image_base64 = self.image_to_base64(image)
                    paragraphs = self.chunk_page_with_gpt(
                        image_base64, page_number, pdf_name
                    )

                    # wstępne obiekty Chunk
                    for chunk_index, content in enumerate(paragraphs):
                        if content.strip():  # ignorowanie pustych
                            chunk_id = f"{Path(pdf_path).stem}_gpt_{page_number}_{chunk_index}"
                            chunk = Chunk(
                                id=chunk_id,
                                pdf_name=pdf_name,
                                page_number=page_number,
                                chunk_index=chunk_index,
                                content=content.strip(),
                            )
                            all_chunks.append(chunk)
                except Exception as e:
                    logger.error(
                        f"Błąd przy przetwarzaniu strony {page_number}: {e}"
                    )
                    continue

            logger.info(f"GPT-4o dało {len(all_chunks)} wstępnych chunków")

            # LangChain splitter
            if len(all_chunks) > 0:
                full_text_parts: List[str] = []
                for chunk in all_chunks:
                    marker = f"\n\n[Strona {chunk.page_number}]\n\n"
                    full_text_parts.append(marker + chunk.content)
                full_text = "".join(full_text_parts)

                text_splitter = RecursiveCharacterTextSplitter(
                    chunk_size=600,
                    chunk_overlap=100,
                    separators=["\n\n", "\n", ". ", " ", ""],
                    keep_separator=True,
                )

                langchain_texts = text_splitter.split_text(full_text)

                final_chunks: List[Chunk] = []
                for i, lang_text in enumerate(langchain_texts):
                    page_match = re.search(r"\[Strona (\d+)\]", lang_text)
                    page_num = int(page_match.group(1)) if page_match else 1

                    clean_content = re.sub(
                        r"\[Strona \d+\]\n*\n*", "", lang_text
                    ).strip()

                    if clean_content:
                        chunk_id = f"{Path(pdf_path).stem}_final_{i}"
                        final_chunk = Chunk(
                            id=chunk_id,
                            pdf_name=pdf_name,
                            page_number=page_num,
                            chunk_index=i,
                            content=clean_content,
                        )
                        final_chunks.append(final_chunk)

                logger.info(
                    f"LangChain po overlap: {len(final_chunks)} finalnych chunków "
                    f"(z {len(all_chunks)} GPT)"
                )
                return final_chunks

            return []

        except Exception as e:
            logger.error(f"Błąd przy przetwarzaniu PDF {pdf_path}: {e}")
            raise
'''
import base64
import json
import logging
import re
from typing import List, Tuple
from pathlib import Path
from io import BytesIO

from pdf2image import convert_from_path
from openai import OpenAI
from langchain_experimental.text_splitter import SemanticChunker
from langchain_huggingface import HuggingFaceEmbeddings

from config import OPENAI_API_KEY
from models import Chunk, OCRResponse

logger = logging.getLogger(__name__)


class PDFChunker:
    """Semantic chunking: OCR(GPT-4o-mini) + embeddingi(lokalne)"""

    def __init__(self, api_key: str = OPENAI_API_KEY):
        self.client = OpenAI(api_key=api_key)
        self.embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        )
        logger.info("PDFChunker: SemanticChunker + lokalne embeddingi")

    def pdf_to_images(self, pdf_path: str) -> List[Tuple[int, any]]:
        try:
            logger.info(f"PDF -> obrazy: {pdf_path}")
            images = convert_from_path(pdf_path)
            return [(i + 1, img) for i, img in enumerate(images)]
        except Exception as e:
            logger.error(f"Błąd PDF->obrazy: {e}")
            raise

    def image_to_base64(self, image) -> str:
        try:
            buffered = BytesIO()
            image.save(buffered, format="PNG")
            return base64.b64encode(buffered.getvalue()).decode("utf-8")
        except Exception as e:
            logger.error(f"Błąd obraz->base64: {e}")
            raise

    def ocr_page(self, image_base64: str, page_number: int, pdf_name: str) -> List[str]:
        """
        OCR strony -> lista tekstu (vision-safe + fallback)
        """
        prompt = (
            "Wyodrębnij dokładny tekst z tej strony jako listę akapitów. "
            "Zwróć TYLKO JSON: {\"text\": [\"akapit1\", \"akapit2\"]}. "
            "Jeśli akapit na końcu strony się na przecinku lub bez kropki, to dodaj do niego pierwszy akapit następnej strony."
            "Bez ```, bez wyjaśnień, bez markdown."
        )

        try:
            logger.info(f"OCR strona {page_number}/{pdf_name}")
            completion = self.client.chat.completions.create(
                model="gpt-4o-mini",
                max_tokens=4000,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}"}},
                        {"type": "text", "text": prompt},
                    ]
                }],
            )

            # VISION-SAFE: różne struktury odpowiedzi
            if not completion.choices or len(completion.choices) == 0:
                logger.warning(f"Pusta odpowiedź GPT strona {page_number}")
                return []

            first_choice = completion.choices
            
            # Obsługa różnych formatów odpowiedzi
            if hasattr(first_choice, 'message') and first_choice.message:
                content_parts = first_choice.message.content
            elif hasattr(first_choice, 'content'):
                content_parts = first_choice.content
            else:
                logger.warning(f"Nieznana struktura odpowiedzi strona {page_number}: {first_choice}")
                return []

            # Zamiana na tekst (vision-safe)
            if isinstance(content_parts, list):
                response_text = "".join(
                    getattr(part, "text", str(part)) 
                    for part in content_parts
                    if hasattr(part, 'text') or isinstance(part, str)
                )
            else:
                response_text = str(content_parts)

            # Czyszczenie JSON
            if "```json" in response_text:
                response_text = response_text.split("```json", 1)[1].split("```", 1)[0]
            elif "```" in response_text:
                parts = response_text.split("```")
                if len(parts) >= 3:
                    response_text = parts[1]

            response_text = response_text.strip()
            logger.debug(f"OCR raw (str {page_number}): {repr(response_text[:200])}")
            
            # Pydantic + solidny fallback
            try:
                data = json.loads(response_text)
                ocr_result = OCRResponse(**data)
                logger.debug(f"OCR strona {page_number}: {len(ocr_result.text)} akapitów")
                return ocr_result.text
            except Exception as pydantic_e:
                logger.warning(f"Pydantic fail strona {page_number}: {pydantic_e}")
                try:
                    data = json.loads(response_text)
                    paragraphs = data.get("text", [])
                    logger.info(f"OCR fallback strona {page_number}: {len(paragraphs)}")
                    return paragraphs
                except json.JSONDecodeError as json_e:
                    logger.error(f"JSON fail OCR strona {page_number}: {json_e}")
                    return []

        except Exception as e:
            logger.error(f"OCR pełny błąd strona {page_number}: {e}")
            return []

    def process_pdf_semantic(self, pdf_path: str) -> List[Chunk]:
        """OCR + Semantic chunking (pełny pipeline)"""
        pdf_name = Path(pdf_path).name
        all_chunks: List[Chunk] = []

        try:
            logger.info(f"Semantic processing: {pdf_name}")
            
            # 1. OCR wszystkich stron
            images = self.pdf_to_images(pdf_path)
            raw_texts = []
            total_pages = len(images)
            # for number, image in images:
            #    image.save(f"{number}_page.png")
            
            for page_number, image in images:
                image_base64 = self.image_to_base64(image)
                page_texts = self.ocr_page(image_base64, page_number, pdf_name)
                raw_texts.extend(page_texts)
                logger.info(f"OCR progress: {page_number}/{total_pages} ")
            
            if not raw_texts:
                logger.warning(f"Brak tekstu OCR: {pdf_name}")
                return []
            
            full_text = "\n\n".join(raw_texts)
            logger.info(f"OCR OK: {len(raw_texts)} akapitów, {len(full_text)} znaków")
            
            # 2. Semantic chunking (lokalne embeddingi)
            logger.info("Semantic chunking...")
            text_splitter = SemanticChunker(
                self.embeddings,
                breakpoint_threshold_type="percentile",
                breakpoint_threshold_amount=92,
            )
            
            semantic_chunks = text_splitter.split_text(full_text)
            
            # 3. Konwersja na Chunk
            for i, content in enumerate(semantic_chunks):
                if content.strip():
                    chunk_id = f"{Path(pdf_path).stem}_semantic_{i}"
                    chunk = Chunk(
                        id=chunk_id,
                        pdf_name=pdf_name,
                        page_number=1,  # semantic nie śledzi stron
                        chunk_index=i,
                        content=content.strip(),
                    )
                    all_chunks.append(chunk)
            
            logger.info(f"Semantic DONE: {len(all_chunks)} chunków gotowych!")
            return all_chunks
            
        except Exception as e:
            logger.error(f"Semantic fail {pdf_path}: {e}")
            raise

