from opensearchpy import OpenSearch

host = 'localhost'
port = 9200
auth = ('admin', 'admin') # For testing only. Don't store credentials in code.
ca_certs_path = '/full/path/to/root-ca.pem' # Provide a CA bundle if you use intermediate CAs with your root CA.

# Create the client with SSL/TLS enabled, but hostname verification disabled.
client = OpenSearch(
    hosts = [{'host': host, 'port': port}],
    http_compress = True, # enables gzip compression for request bodies
    http_auth = auth,
    use_ssl = False,
    verify_certs = False,
    ssl_assert_hostname = False,
    ssl_show_warn = False,
    ca_certs = ca_certs_path
)




index_name = 'python-test-index'
index_body = {
  'settings': {
    'index': {
      "mappings": {
        "properties": {
          "title": { "type": "text" },
          "content": { "type": "text" }
        }
      }
    }
  }
}

response = client.indices.create(index=index_name, body=index_body)

print(response)





document = {

  "title": "Exploring the Sahara Desert", "content": "Sand dunes and vast landscapes.",
  #"title": "Amazon Rainforest Tour", "content": "Dense jungle and exotic wildlife.",
  #"title": "Mountain Adventures", "content": "Snowy peaks and hiking trails."
}


response = client.index(
    index = 'python-test-index',
    body = document,
    refresh = True
)

print(response)




q = 'miller'
query = {
  "more_like_this": {
    "fields": ["content"],
    "like": "jungle wildlife",
    "min_term_freq": 1,
   "min_doc_freq": 1
  }
}

response = client.search(
    body = query,
    index = 'python-test-index'
)

print(response)