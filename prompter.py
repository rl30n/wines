import argparse
import json
import time
from elasticsearch import Elasticsearch
import requests
import logging
import ecs_logging
import os
from logging.handlers import TimedRotatingFileHandler, RotatingFileHandler
from pathlib import Path

# --- Config ---
ES_HOST = "https://localhost:9200"
ES_USER = "elastic"
ES_PASS = "changeme"
INDEX_NAME = "vinos_embeddings"

# --- Logger ---
logger = logging.getLogger("vinosearch")

log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)
log_file_path = log_dir / "prompter.log"

file_handler = TimedRotatingFileHandler(
    filename=log_file_path,
    when="midnight",
    interval=1,
    backupCount=7,
    encoding='utf-8',
    utc=True
)
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(ecs_logging.StdlibFormatter())
logger.addHandler(file_handler)  # logger de fichero añadido

logging.getLogger().addHandler(file_handler)  # logger root, opcional

# --- Argumentos CLI ---
parser = argparse.ArgumentParser(description="Consulta RAG al índice de vinos.")
parser.add_argument("prompt", type=str, help="Pregunta para generar embedding y consultar.")
parser.add_argument("--debug", action="store_true", help="Activa salida de logging en modo debug")
args = parser.parse_args()

if args.debug:
    handler = logging.StreamHandler()
    handler.setFormatter(ecs_logging.StdlibFormatter())
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    logging.getLogger().setLevel(logging.DEBUG)  # nivel DEBUG añadido al logger root

# --- Generador de embeddings con Mistral ---
def generate_embedding(prompt):
    logger.debug("Generando embedding con Mistral para prompt: %s", prompt)
    url = "http://localhost:11434/api/embeddings"
    payload = {
        "model": "mistral",
        "prompt": prompt
    }
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
        embedding = data.get("embedding", [])
        if not embedding:
            raise ValueError("El embedding generado está vacío.")
        logger.debug("Embedding generado (primeros valores): %s", embedding[:5])
        return embedding
    except Exception as e:
        logger.exception("Error al generar el embedding desde Mistral: %s", e)
        raise

# --- Query Elasticsearch con knn ---
def search_vinos(embedding):
    client = Elasticsearch(ES_HOST, basic_auth=(ES_USER, ES_PASS), verify_certs=False)

    query = {
        "knn": {
            "field": "combined_text_embedding",
            "query_vector": embedding,
            "k": 5,
            "num_candidates": 100
        }
    }

    logger.debug("Consultando Elasticsearch con query:\n%s", json.dumps(query, indent=2))
    try:
        res = client.search(index=INDEX_NAME, body=query)
        logger.debug("Respuesta cruda de Elasticsearch:\n%s", json.dumps(res.body, indent=2, default=str))
        return res["hits"]["hits"]
    except Exception as e:
        logger.exception("Error en la consulta a Elasticsearch: %s", e)
        raise

# --- Generar respuesta con contexto ---
def generate_answer_with_context(prompt, context_docs):
    import time
    start_time = time.time()
    
    context_texts = "\n\n".join(
        f"- {doc['_source'].get('wine_description', '')}" for doc in context_docs
    )
    
    if args.debug:
        print("\n📄 Documentos del contexto:")
        for i, doc in enumerate(context_docs, 1):
            print(f"\nDocumento {i}:")
            print(json.dumps(doc["_source"], indent=2, ensure_ascii=False))

    context_duration = time.time() - start_time
    logger.debug("Tiempo de construcción del contexto: %.2f segundos", context_duration)
    if args.debug:
        print(f"\n⏱️ Tiempo de construcción del contexto: {context_duration:.2f} segundos")

    composed_prompt = (
        f"Teniendo en cuenta la siguiente información sobre vinos:\n\n{context_texts}\n\n"
        f"Responde a la siguiente pregunta de forma precisa y experta como somelier:\n\n{prompt}"
    )

    logger.debug("Prompt enviado a Mistral con contexto:\n%s", composed_prompt[:1000])

    url = "http://localhost:11434/api/generate"
    payload = {
        "model": "mistral",
        "prompt": composed_prompt,
        "stream": False
    }

    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
        final_answer = data.get("response", "").strip()
        logger.debug("Respuesta final generada por Mistral:\n%s", final_answer)
        return final_answer
    except Exception as e:
        logger.exception("Error generando respuesta con contexto en Mistral: %s", e)
        raise

# --- Main ---
embedding = generate_embedding(args.prompt)
results = search_vinos(embedding)

logger.debug("\nTop resultados:\n")
for hit in results:
    logger.debug("Resultado: %s", hit)

final_answer = generate_answer_with_context(args.prompt, results)
print("\n🧠 Respuesta generada por Mistral:")
print(final_answer)
