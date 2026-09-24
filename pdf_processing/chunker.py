from typing import List, Dict, Tuple, Optional, Union, Iterable
import fitz  # PyMuPDF
from dataclasses import dataclass, field
from collections import Counter
from collections import defaultdict
import re
import os

TEXT_BLOCK_TYPE: int = 0

@dataclass
class TextSegment:
    x0: int
    y0: int
    x1: int
    y1: int
    text: str
    font: str
    font_size: int
    block_id: int
    page_no: int

@dataclass
class TextBlock:
    x0: int
    y0: int
    x1: int
    y1: int
    text: str
    font: str
    font_size: int
    block_id: int
    page_no: int

@dataclass
class ChunkedPdfWithTextBlock:
    name: str = ''
    path: str = ''
    chunks: List[TextBlock] = field(default_factory=list)

@dataclass
class ChunkedPdf:
    name: str = ''
    path: str = ''
    chunks: List[str] = field(default_factory=list)

def get_font_and_size_from_block(block: Dict) -> Optional[Tuple[List[Tuple[str, int]], bool]]:
    if block["type"] != TEXT_BLOCK_TYPE:
        return None

    font_data: List[Tuple[str, int]] = []
    line_with_intro: bool            = False
    
    for line in block["lines"]:
        for span in line["spans"]:
            if "introduction" in span["text"].lower():
                line_with_intro = True
            else:
                font_data.append((span["font"], round(span["size"], 1)))
            # print(f"FROM FIUNCTION: {span["font"]}, {round(span["size"], 1)}")
            
    return (font_data, line_with_intro)

def get_most_likley_font_and_size(pdf_path: str) -> Tuple[str, float]:
    doc = fitz.open(pdf_path)
    font_size_counter = Counter()

    pages = doc[:-1] if len(doc) > 1 else doc

    for page in pages:
        blocks = page.get_text("dict").get("blocks", [])

        for block in blocks:
            data = get_font_and_size_from_block(block)

            if not data:
                continue

            font_data, intro_found = data

            if intro_found and font_data:
                return Counter(font_data).most_common(1)[0][0]

            font_size_counter.update(font_data)

    if not font_size_counter:
        raise ValueError(
            f"Nie znaleziono tekstu ani danych o czcionkach w PDF: {pdf_path}"
        )

    return font_size_counter.most_common(1)[0][0]

def get_text_block(block: Dict, page_number: int) -> Optional[List[TextSegment]]:
    if block["type"] != TEXT_BLOCK_TYPE:
        return None

    filtered_segments: List[TextSegment] = []
    for line in block["lines"]:
        for span in line["spans"]:            
            filtered_segments.append(
                TextSegment(
                    *span["bbox"],
                    span["text"],
                    span["font"],
                    round(span["size"], 1),
                    block["number"],
                    page_number
                )
            )
            
    return filtered_segments

def get_text_segments(pdf_path: str) -> List[TextSegment]:
    doc = fitz.open(pdf_path)

    segments: List[TextSegment] = []
    
    for page in doc:
        blocks = page.get_text("dict")["blocks"]
        
        for block in blocks:
            s = get_text_block(block, page.number)
            if s:
                segments.extend(s)

    return segments            

def replace_special_characters(text: str) -> str:
    text = text.replace("\xad", "")
    text = text.replace("\u00ad", "")
    text = text.replace("\N{SOFT HYPHEN}", "")

    # remove all "- " surrounded by characters
    text = re.sub(r"(?<=.)- (?=.)", "", text)
    
    return text


def aggregate_segments_to_blocks(segments: List[TextSegment]) -> List[TextBlock]:
    """
    Groups individual TextSegments by page and block_id, 
    merging them into complete TextBlock objects.
    """
    # Group segments using a dictionary keyed by (page_no, block_id)
    grouped_segments = defaultdict(list)
    for seg in segments:
        grouped_segments[(seg.page_no, seg.block_id)].append(seg)
    
    blocks = []
    for (page_no, block_id), segs in grouped_segments.items():
        # Identify the bounding box for the entire block
        x0 = min(s.x0 for s in segs)
        y0 = min(s.y0 for s in segs)
        x1 = max(s.x1 for s in segs)
        y1 = max(s.y1 for s in segs)
        
        # Join text - assuming segments in the list are already in reading order 
        # from PyMuPDF's internal extraction.
        full_text = " ".join(s.text.strip() for s in segs if s.text.strip())
        
        # Take the font and size of the first segment as representative of the block
        representative = segs[0]
        
        blocks.append(
            TextBlock(
                x0=x0, 
                y0=y0, 
                x1=x1, 
                y1=y1,
                text=full_text,
                font=representative.font,
                font_size=representative.font_size,
                block_id=block_id,
                page_no=page_no
            )
        )
    return blocks
    
def sort_blocks_columnar_order(blocks: List[TextBlock], column_margin: int = 50) -> List[TextBlock]:
    """
    Sorts TextBlocks by page, then by column (Left-to-Right), 
    then top-to-bottom within each column.
    
    Args:
        blocks: List of aggregated TextBlock objects.
        column_margin: Pixel threshold to group blocks into the same column. 
                       50-100 is usually ideal for standard PDFs to ignore minor indentations.
    """
    return sorted(blocks, key=lambda b: (
        b.page_no, 
        b.x0 // column_margin,  # Secondary Sort: Groups x0 into distinct vertical "columns"
        b.y0                    # Tertiary Sort: Top-to-bottom inside that specific column
    ))

def get_processed_blocks(pdf_path: str) -> List[TextBlock]:
    """
    Main pipeline to execute the extraction, aggregation, and sorting.
    """
    most_likley_font_and_size: Tuple[str, int] = get_most_likley_font_and_size(pdf_path)
    segments = get_text_segments(pdf_path)

    filtered_segments = list(filter(
        lambda s: s.font == most_likley_font_and_size[0] and s.font_size == most_likley_font_and_size[1],     
        segments
    ))
    
    blocks = aggregate_segments_to_blocks(filtered_segments)
    return sort_blocks_columnar_order(blocks, column_margin=50)

def get_glued_str_only_blocks(sorted_blocks: List[TextBlock]) -> List[str]:
    output_string_blocks: List[str] = []
    
    block_index: int = 0
    current_tmp: str = ''
    while block_index < len(sorted_blocks):
        current_tmp += sorted_blocks[block_index].text + ' '
        if sorted_blocks[block_index].text.endswith("."):
            output_string_blocks.append(replace_special_characters(current_tmp.strip()))
            current_tmp = ''

        block_index += 1

    if current_tmp:
        output_string_blocks.append(replace_special_characters(current_tmp.strip()))
    
    return output_string_blocks

def chunk_pdf_to_blocks(pdf_paths: Union[str, List[str]]) -> List[ChunkedPdfWithTextBlock]:
    if isinstance(pdf_paths, str):
        return [ 
            ChunkedPdfWithTextBlock(
                name   = os.path.split(pdf_paths)[1],
                path   = pdf_paths,
                chunks = get_processed_blocks(pdf_paths)
            )
        ]
    elif isinstance(pdf_paths, Iterable):
        return [
             ChunkedPdfWithTextBlock(
                name   = os.path.split(pdf_path)[1],
                path   = pdf_path,
                chunks = get_processed_blocks(pdf_path)
            )
                for pdf_path in pdf_paths
        ]
    return [] # in case of wrong type


def chunk_pdf_to_strings(pdf_paths: Union[str, List[str]]) -> List[ChunkedPdf]:
    if isinstance(pdf_paths, str):
        return [ 
            ChunkedPdf(
                name   = os.path.split(pdf_paths)[1],
                path   = pdf_paths,
                chunks = get_glued_str_only_blocks(
                    get_processed_blocks(pdf_paths)
                )
            )
        ]
    elif isinstance(pdf_paths, Iterable):
        return [
             ChunkedPdf(
                name   = os.path.split(pdf_path)[1],
                path   = pdf_path,
                chunks = get_glued_str_only_blocks(
                    get_processed_blocks(pdf_path)
                )
            )
                for pdf_path in pdf_paths
        ]
    return [] # in case of wrong type