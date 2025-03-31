import requests
from elasticsearch import Elasticsearch, helpers
from elasticsearch.helpers import BulkIndexError
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configuración Elasticsearch
es = Elasticsearch("https://localhost:9200", basic_auth=("elastic", "changeme"), verify_certs=False)
index_name = "vinos_embeddings"
batch_size = 10

# Configuración Ollama local
OLLAMA_URL = "http://localhost:11434/api/embeddings"
MODEL_NAME = "mistral"

def get_embedding(text):
    response = requests.post(
        OLLAMA_URL,
        json={"model": MODEL_NAME, "prompt": text},
    )
    response.raise_for_status()
    return response.json()["embedding"]

def fetch_documents():
    resp = helpers.scan(es, index=index_name, query={"query": {"match_all": {}}})
    for doc in resp:
        yield doc

def main():
    bulk_buffer = []
    counter = 0

    for doc in fetch_documents():
        doc_id = doc["_id"]
        source = doc["_source"]
        updated_fields = {}

        # Embeddings recomendados
        text_fields = {
            "wine_name": source.get("wine_name", ""),
            "wine_description": source.get("wine_description", ""),
            "winery": source.get("winery", ""),
            "vinification": source.get("vinification", ""),
            "sensory_profile.cata_visual": source.get("sensory_profile", {}).get("cata_visual", ""),
            "sensory_profile.cata_olfativa": source.get("sensory_profile", {}).get("cata_olfativa", ""),
            "sensory_profile.cata_gustativa": source.get("sensory_profile", {}).get("cata_gustativa", ""),
            "sensory_profile.maridaje": source.get("sensory_profile", {}).get("maridaje", ""),
            "info_table.variety_table": " ".join(source.get("info_table", {}).get("variety_table", [])),
        }

        for field, text in text_fields.items():
            if text:
                embedding = get_embedding(text)
                embedding_field = f"{field.replace('.', '_')}_embedding"
                updated_fields[embedding_field] = embedding

        bulk_buffer.append({
            "_op_type": "update",
            "_index": index_name,
            "_id": doc_id,
            "doc": updated_fields
        })

        counter += 1
        if len(bulk_buffer) >= batch_size:
            try:
                helpers.bulk(es, bulk_buffer)
                print(f"✅ {counter} documentos procesados.")
            except BulkIndexError as e:
                for error in e.errors:
                    print(f"Error al procesar documento {error['update']['_id']}: {error['update']['error']}")
            bulk_buffer.clear()

    if bulk_buffer:
        try:
            helpers.bulk(es, bulk_buffer)
            print(f"✅ Procesados los últimos {len(bulk_buffer)} documentos.")
        except BulkIndexError as e:
            for error in e.errors:
                print(f"Error al procesar documento {error['update']['_id']}: {error['update']['error']}")

if __name__ == "__main__":
    main()