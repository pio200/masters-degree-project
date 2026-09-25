import os

from dotenv import load_dotenv
from opensearchpy import OpenSearch

from utils.embeddings import EMBEDDING_DIMENSION, LocalEmbedder


load_dotenv()

class OpenSearchIndexer:
    def __init__(self, 
                 host = None,
                 port = None,
                 auth = None,
                 ca_certs_path = '/full/path/to/root-ca.pem',
                 index_name = None,
                 use_embeddings = True
                 ):
        host = host or os.getenv("OPENSEARCH_HOST", "localhost")
        port = port or int(os.getenv("OPENSEARCH_PORT", "9200"))
        auth = auth or (
            os.getenv("OPENSEARCH_USER", "admin"),
            os.getenv("OPENSEARCH_PASSWORD", "admin"),
        )
        self.host = host
        self.port = port
        self.auth = auth
        self.ca_certs_path = ca_certs_path

        self.client = OpenSearch(
            hosts = [{'host': host, 'port': port}],
            http_compress = True, # enables gzip compression for request bodies
            http_auth = auth,
            use_ssl = False,
            verify_certs = False,
            ssl_assert_hostname = False,
            ssl_show_warn = False,
            ca_certs = ca_certs_path
        )

        # self.index_name = 'os-index-knn'
        # self.index_body = {
        #     'settings': {
        #         'index': {
        #             "knn": True
        #         }
        #     },    
        #     "mappings": {
        #         "properties": {
        #             "title": { "type": "text" },
        #             "chunk_id": { "type": "integer" },
        #             "content": { "type": "text" },
        #             "embedding":{ 
        #                 "type": "knn_vector",
        #                 "dimension": 512
        #             }
        #         }
        #     } 
        # }


        self.index_name = index_name or os.getenv("OPENSEARCH_INDEX", "os-index-knn")
        self.use_embeddings = use_embeddings
        self.embedder = LocalEmbedder() if use_embeddings else None
        self.index_body = {
            'settings': {
                'index': {
                    'knn': True
                }
            },    
            "mappings": {
                "properties": {
                    "title": { "type": "text" },
                    "chunk_id": { "type": "integer" },
                    "content": { "type": "text" },
                    "embedding": {
                        "type": "knn_vector",
                        "dimension": EMBEDDING_DIMENSION
                    }
                }
            } 
        }

        if not self.client.indices.exists(index=self.index_name):
            self.client.indices.create(
                index=self.index_name,
                body=self.index_body
            )
            print(f"Utworzono indeks: {self.index_name}")
        else:
            print(f"Indeks już istnieje: {self.index_name}")
    

    def send_chunk(self, title, chunk_id, content, embedding=None):
        if self.use_embeddings and embedding is None:
            embedding = self.embedder.encode([content])[0]

        body = {
            "title": title,
            "chunk_id": chunk_id,
            "content": content
        }
        if embedding is not None:
            body["embedding"] = embedding


        return self.client.index(
            index = self.index_name,
            body = body,
            refresh = True
        )
    
    def query(self, query):
        return self.client.search(
            body = query,
            index = self.index_name
        )
