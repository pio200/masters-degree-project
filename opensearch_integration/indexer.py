from opensearchpy import OpenSearch

class OpenSearchIndexer:
    def __init__(self, 
                 host = "localhost", 
                 port = 9200, 
                 auth = ('admin', 'admin'), # For testing only. Don't store credentials in code., 
                 ca_certs_path = '/full/path/to/root-ca.pem' # Provide a CA bundle if you use intermediate CAs with your root CA.
                 ):
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


        self.index_name = 'os-index'
        self.index_body = {
            'settings': {
                'index': {

                }
            },    
            "mappings": {
                "properties": {
                    "title": { "type": "text" },
                    "chunk_id": { "type": "integer" },
                    "content": { "type": "text" },
                    # "embedding":{ 
                    #     "type": "knn_vector",
                    #     "dimension": 512
                    # }
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
    

    def send_chunk(self, title, chunk_id, content):

        body = {
            "title": title,
            "chunk_id": chunk_id,
            "content": content
        }


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
