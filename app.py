import json
import os
from typing import Any, Dict, List

import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI
from opensearchpy import OpenSearch

from utils.embeddings import LocalEmbedder


load_dotenv()

OPENSEARCH_INDEX = os.getenv("OPENSEARCH_INDEX", "os-index-knn")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
KNN_FIELD = os.getenv("OPENSEARCH_KNN_FIELD", "embedding")


@st.cache_resource
def get_local_embedder() -> LocalEmbedder:
    return LocalEmbedder()


def get_opensearch_client() -> OpenSearch:
    """Create a client matching the connection used by the indexing script."""
    return OpenSearch(
        hosts=[
            {
                "host": os.getenv("OPENSEARCH_HOST", "localhost"),
                "port": int(os.getenv("OPENSEARCH_PORT", "9200")),
            }
        ],
        http_compress=True,
        http_auth=(
            os.getenv("OPENSEARCH_USER", "admin"),
            os.getenv("OPENSEARCH_PASSWORD", "admin"),
        ),
        use_ssl=False,
        verify_certs=False,
        ssl_assert_hostname=False,
        ssl_show_warn=False,
    )


def get_query_embedding(query: str) -> List[float]:
    return get_local_embedder().encode([query])[0]


def search_evidence(
    query: str, size: int = 8, search_method: str = "content^3"
) -> List[Dict[str, Any]]:
    """Find relevant indexed passages using the selected OpenSearch strategy."""
    if search_method == "more-like-this":
        search_query = {
            "more_like_this": {
                "fields": ["content"],
                "like": query,
                "min_term_freq": 1,
                "min_doc_freq": 1,
                "max_query_terms": 25,
            }
        }
    elif search_method == "kNN":
        search_query = {
            "knn": {
                KNN_FIELD: {
                    "vector": get_query_embedding(query),
                    "k": size,
                }
            }
        }
    else:
        search_query = {
            "multi_match": {
                "query": query,
                "fields": ["content^3", "title"],
                "type": "best_fields",
            }
        }

    response = get_opensearch_client().search(
        index=OPENSEARCH_INDEX,
        body={
            "size": size,
            "query": search_query,
        },
    )
    return response.get("hits", {}).get("hits", [])


def build_differential(query: str, hits: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Ask GPT to rank a differential diagnosis using only retrieved evidence."""
    evidence = "\n\n".join(
        f"Evidence {index}: {hit.get('_source', {}).get('content', '')}"
        for index, hit in enumerate(hits, start=1)
    )
    prompt = f"""
You are assisting a radiologist with a preliminary literature-based differential diagnosis.
This is decision support, not a diagnosis. Use only the patient's description and the
retrieved evidence below. Do not invent findings, citations, or certainty.

Patient/image description:
{query}

Retrieved evidence:
{evidence}

Return valid JSON with exactly one key, "diagnoses", containing exactly three objects.
Each object must have these string keys:
- "name": diagnosis name
- "reason": one concise reason tied to the description or evidence
- "next_step": one useful confirmatory imaging, clinical, or laboratory step
- "confidence": "high", "moderate", or "low"
Rank the objects from most to least probable. If the evidence is insufficient, say so
in the reasons and keep confidence low. Do not include markdown.
""".strip()

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        temperature=0.1,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": "Return only the requested JSON object.",
            },
            {"role": "user", "content": prompt},
        ],
    )
    payload = json.loads(response.choices[0].message.content or "{}")
    diagnoses = payload.get("diagnoses", [])
    if not isinstance(diagnoses, list) or len(diagnoses) != 3:
        raise ValueError("GPT returned an invalid differential diagnosis format.")
    return diagnoses


def render_diagnosis(diagnosis: Dict[str, str], rank: int) -> None:
    st.subheader(f"{rank}. {diagnosis.get('name', 'Unspecified')}")
    st.caption(f"Confidence: {diagnosis.get('confidence', 'unknown').title()}")
    st.write(diagnosis.get("reason", "No rationale provided."))
    st.markdown(f"**Suggested next step:** {diagnosis.get('next_step', 'Not specified.')}")


def main() -> None:
    st.set_page_config(
        page_title="Radiology Differential Assistant",
        page_icon="+",
        layout="wide",
    )
    st.title("Radiology Differential Assistant")
    st.write("Search indexed radiology references and generate a three-item preliminary differential.")
    st.warning(
        "For clinical decision support only. Verify every result with the complete study, "
        "patient history, and local clinical protocols. Do not enter identifying patient data."
    )

    description = st.text_area(
        "Image description",
        height=180,
        placeholder="Example: Well-defined solitary pulmonary nodule in the right upper lobe...",
    )
    search_method = st.selectbox(
        "Search method",
        options=["content^3", "more-like-this", "kNN"],
        help=(
            "content^3 uses keyword relevance.  \n"
            "more-like-this finds documents with similar terms.  \n"
            "kNN uses local semantic embeddings and requires an embedding field in OpenSearch."
        ),
    )
    search_count = st.slider("Reference passages", min_value=3, max_value=12, value=8)

    if st.button("Search and generate differential", type="primary", disabled=not description.strip()):
        if not os.getenv("OPENAI_API_KEY"):
            st.error("OPENAI_API_KEY is not configured.")
            return

        try:
            with st.spinner("Searching radiology references..."):
                hits = search_evidence(
                    description.strip(),
                    size=search_count,
                    search_method=search_method,
                )
            if not hits:
                st.info("No matching passages were found in OpenSearch.")
                return

            with st.spinner("Preparing the differential diagnosis..."):
                diagnoses = build_differential(description.strip(), hits)

            st.header("Preliminary differential")
            for rank, diagnosis in enumerate(diagnoses, start=1):
                render_diagnosis(diagnosis, rank)

            st.header("Retrieved evidence")
            for index, hit in enumerate(hits, start=1):
                source = hit.get("_source", {})
                title = source.get("title", "Indexed reference")
                with st.expander(f"{index}. {title}"):
                    st.write(source.get("content", "No content returned."))
                    st.caption(f"Search score: {hit.get('_score', 'n/a')}")
        except Exception as error:
            st.error(f"Unable to complete the search: {error}")


if __name__ == "__main__":
    main()