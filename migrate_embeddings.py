import argparse
import os
from typing import Dict, List

from opensearchpy import helpers

from opensearch_integration.indexer import OpenSearchIndexer


def migrate(source_index: str, target_index: str, batch_size: int) -> int:
    print("Loading local embedding model...", flush=True)
    indexer = OpenSearchIndexer(index_name=target_index, use_embeddings=True)
    documents: List[Dict] = []
    migrated = 0

    print(f"Scanning {source_index}...", flush=True)
    for hit in helpers.scan(
        indexer.client,
        index=source_index,
        query={"query": {"match_all": {}}},
    ):
        source = hit.get("_source", {})
        content = source.get("content", "").strip()
        if not content:
            continue

        documents.append(
            {
                "_id": hit["_id"],
                "title": source.get("title", ""),
                "chunk_id": source.get("chunk_id", 0),
                "content": content,
            }
        )

        if len(documents) >= batch_size:
            migrated += _index_batch(indexer, documents)
            documents = []

    if documents:
        migrated += _index_batch(indexer, documents)

    indexer.client.indices.refresh(index=target_index)
    return migrated


def _index_batch(indexer: OpenSearchIndexer, documents: List[Dict]) -> int:
    vectors = indexer.embedder.encode(document["content"] for document in documents)
    actions = [
        {
            "_op_type": "index",
            "_index": indexer.index_name,
            "_id": document["_id"],
            "_source": {
                "title": document["title"],
                "chunk_id": document["chunk_id"],
                "content": document["content"],
                "embedding": vector,
            },
        }
        for document, vector in zip(documents, vectors)
    ]
    helpers.bulk(indexer.client, actions)
    print(f"Indexed {len(actions)} documents into {indexer.index_name}")
    return len(actions)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Copy text chunks into a local-embedding kNN index."
    )
    parser.add_argument(
        "--source-index",
        default=os.getenv("OPENSEARCH_SOURCE_INDEX", "os-index"),
    )
    parser.add_argument(
        "--target-index",
        default=os.getenv("OPENSEARCH_INDEX", "os-index-knn"),
    )
    parser.add_argument("--batch-size", type=int, default=32)
    args = parser.parse_args()

    count = migrate(args.source_index, args.target_index, args.batch_size)
    print(f"Migration complete: {count} documents")