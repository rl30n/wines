import requests
from elasticsearch import Elasticsearch, helpers
from elasticsearch.helpers import BulkIndexError
import urllib3
import argparse
import logging
import ecs_logging
from logging.handlers import TimedRotatingFileHandler
import os

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

parser = argparse.ArgumentParser()
parser.add_argument("--debug", action="store_true", help="Activar logging de depuración")
args = parser.parse_args()

logger = logging.getLogger("vinosearch")
handler = logging.StreamHandler()
handler.setFormatter(ecs_logging.StdlibFormatter())
logger.addHandler(handler)
logger.setLevel(logging.DEBUG if args.debug else logging.INFO)

os.makedirs("logs", exist_ok=True)
file_handler = TimedRotatingFileHandler("logs/enrichment.log", when="midnight", backupCount=7)
file_handler.setFormatter(ecs_logging.StdlibFormatter())
logger.addHandler(file_handler)

# Configuración Elasticsearch
es = Elasticsearch("https://localhost:9200", basic_auth=("elastic", "changeme"), verify_certs=False)
index_name = "vinos_embeddings"
batch_size = 10

# Configuración Ollama local
OLLAMA_URL = "http://localhost:11434/api/embeddings"
MODEL_NAME = "mistral"
session = requests.Session()

def get_embedding(text):
    response = session.post(
        OLLAMA_URL,
        json={"model": MODEL_NAME, "prompt": text},
    )
    logger.debug("Generando embedding para texto: %s", text)
    response.raise_for_status()
    emb = response.json()["embedding"]
    logger.debug("Embedding generado: %s", emb)
    return emb

def fetch_documents():
    logger.debug("Iniciando escaneo de documentos desde el índice '%s'", index_name)
    return helpers.scan(es, index=index_name, query={"query": {"match_all": {}}}, scroll="5m")

def process_document(doc):
    doc_id = doc["_id"]
    updated_fields = {}

    text_fields = {
        "combined_text": doc["_source"].get("combined_text", ""),
        "wine_name": doc["_source"].get("wine_name", ""),
        "wine_description": doc["_source"].get("wine_description", ""),
        "winery": doc["_source"].get("winery", ""),
        "vinification": doc["_source"].get("vinification", ""),
        "sensory_profile.cata_visual": doc["_source"].get("sensory_profile", {}).get("cata_visual", ""),
        "sensory_profile.cata_olfativa": doc["_source"].get("sensory_profile", {}).get("cata_olfativa", ""),
        "sensory_profile.cata_gustativa": doc["_source"].get("sensory_profile", {}).get("cata_gustativa", ""),
        "sensory_profile.maridaje": doc["_source"].get("sensory_profile", {}).get("maridaje", ""),
        "info_table.variety_table": " ".join(doc["_source"].get("info_table", {}).get("variety_table", [])),
    }

    for field, text in text_fields.items():
        if text:
            embedding = get_embedding(text)
            embedding_field = f"{field.replace('.', '_')}_embedding"
            updated_fields[embedding_field] = embedding

    logger.debug("Documento procesado ID=%s con campos: %s", doc_id, list(updated_fields.keys()))
    return {
        "_op_type": "update",
        "_index": index_name,
        "_id": doc_id,
        "doc": updated_fields
    }

def main():
    bulk_buffer = []
    counter = 0

    for doc in fetch_documents():
        bulk_buffer.append(process_document(doc))
        counter += 1

        if len(bulk_buffer) >= batch_size:
            try:
                helpers.bulk(es, bulk_buffer, timeout="10s")
                logger.debug("Bulk insert exitoso con %d documentos", len(bulk_buffer))
                print(f"✅ {counter} documentos procesados.")
                bulk_buffer.clear()
            except BulkIndexError as e:
                logger.error("Error al procesar documentos en bulk: %s", e)
                for error in e.errors:
                    print(f"Error al procesar documento {error['update']['_id']}: {error['update']['error']}")

    if bulk_buffer:
        try:
            helpers.bulk(es, bulk_buffer, timeout="10s")
            logger.debug("Último bulk insert de %d documentos procesado correctamente", len(bulk_buffer))
            print(f"✅ Procesados los últimos {len(bulk_buffer)} documentos.")
        except BulkIndexError as e:
            logger.error("Error al procesar documentos en bulk: %s", e)
            for error in e.errors:
                print(f"Error al procesar documento {error['update']['_id']}: {error['update']['error']}")

if __name__ == "__main__":
    main()