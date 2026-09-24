from opensearchpy import OpenSearch

host = 'some.host.com'
port = 3005
auth = ('joedoe', 'qwerty') 
index_name = 'index_with_custom_analyser'

opensearch_client = OpenSearch(
    hosts = [{'host': host, 'port': port}],
    http_auth = auth,
    use_ssl = True,
    verify_certs = False,
    ssl_assert_hostname = False,
    ssl_show_warn = False,
)

message_alike = "message C#"

query_body = {
  "query": {
    "more_like_this": {
      "fields": ["message"],
      "like": message_alike,
      "min_term_freq": 1,
      "max_query_terms": 12
    }
  },
  "size": 20  
}

results = opensearch_client.search(
            body = query_body,
            index = 'index_with_custom_analyser'
        )

print(results['hits']['hits'])
