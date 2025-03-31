import argparse
from sentence_transformers import SentenceTransformer
import json
from elasticsearch import Elasticsearch
import requests

# --- Config ---
ES_HOST = "https://localhost:9200"
ES_USER = "elastic"
ES_PASS = "changeme"
INDEX_NAME = "vinos_embeddings"

embedding_model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

# --- Argumentos CLI ---
parser = argparse.ArgumentParser(description="Consulta RAG al índice de vinos.")
parser.add_argument("prompt", type=str, help="Pregunta para generar embedding y consultar.")
args = parser.parse_args()

# --- Generador de embeddings con Mistral local ---
def generate_embedding(prompt):
    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": "mistral",
            "prompt": f"embed: {prompt}",
            "stream": False
        }
    )
    response.raise_for_status()
    data = response.json()
    embedding_str = data.get("response", "").strip()
    embedding = json.loads(embedding_str)
    return embedding

# --- Query Elasticsearch con script_score combinando varios campos ---
def search_vinos(embedding):
    client = Elasticsearch(ES_HOST, basic_auth=(ES_USER, ES_PASS), verify_certs=False)

    query = {
        "size": 5,
        "query": {
            "script_score": {
                "query": {"match_all": {}},
                "script": {
                    "source": """
                        double score = 0.0;
                        int count = 0;

                        if (doc.containsKey('wine_description_embedding') && doc['wine_description_embedding'].size() > 0) {
                            score += cosineSimilarity(params.vector, 'wine_description_embedding');
                            count++;
                        }
                        if (doc.containsKey('vinification_embedding') && doc['vinification_embedding'].size() > 0) {
                            score += cosineSimilarity(params.vector, 'vinification_embedding');
                            count++;
                        }
                        if (doc.containsKey('sensory_profile_cata_gustativa_embedding') && doc['sensory_profile_cata_gustativa_embedding'].size() > 0) {
                            score += cosineSimilarity(params.vector, 'sensory_profile_cata_gustativa_embedding');
                            count++;
                        }
                        if (doc.containsKey('sensory_profile_maridaje_embedding') && doc['sensory_profile_maridaje_embedding'].size() > 0) {
                            score += cosineSimilarity(params.vector, 'sensory_profile_maridaje_embedding');
                            count++;
                        }
                        
                        return count > 0 ? score / count : 0.0;
                    """,
                    "params": {
                        "vector": embedding
                    }
                }
            }
        }
    }

    res = client.search(index=INDEX_NAME, body=query)
    return res["hits"]["hits"]

# --- Main ---
embedding = generate_embedding(args.prompt)
results = search_vinos(embedding)

print("\nTop resultados:\n")
for hit in results:
    print(f"Score: {hit['_score']:.4f}")
    print(f"Nombre: {hit['_source'].get('wine_name', 'N/A')}")
    print(f"Bodega: {hit['_source'].get('winery', 'N/A')}")
    print(f"Descripción: {hit['_source'].get('wine_description', '')[:200]}...")
    print("-" * 60)
