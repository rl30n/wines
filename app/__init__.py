from flask import Flask, render_template, request, Blueprint, jsonify
import subprocess
import logging
import ecs_logging
import sys
import os
import argparse
from datetime import datetime
from .routes import main
from elasticsearch import Elasticsearch


ES_HOST = "https://localhost:9200"
ES_USER = "elastic"
ES_PASS = "changeme"
INDEX_NAME = "vinos_embeddings"

# Configuración de logger ECS
logger = logging.getLogger("vinosearch")
logger.setLevel(logging.INFO)  # Nivel global de logging por defecto

log_directory = "logs"
os.makedirs(log_directory, exist_ok=True)
log_file_path = os.path.join(log_directory, "webapp.log")

# Logger para archivo
file_handler = logging.FileHandler(log_file_path)
file_handler.setFormatter(ecs_logging.StdlibFormatter())
logger.addHandler(file_handler)

# Logger para consola
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(ecs_logging.StdlibFormatter())
logger.addHandler(console_handler)

# Inicialización del cliente de Elasticsearch
client = Elasticsearch(ES_HOST, basic_auth=(ES_USER, ES_PASS), verify_certs=False)

# Parser para habilitar modo debug desde el CLI
parser = argparse.ArgumentParser(description="Aplicación Flask con ECS logging")
parser.add_argument("--debug", action="store_true", help="Activa modo debug")
args, unknown = parser.parse_known_args()



if args.debug:
    logger.setLevel(logging.DEBUG)  # Establecer nivel DEBUG cuando se pase el argumento --debug
    logger.debug("Modo debug activado")

# Blueprint de Flask
main = Blueprint('main', __name__)

@main.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        user_query = request.form['query']
        logger.info("Consulta recibida", extra={"user.query": user_query})

        try:
            logger.debug("Llamando a prompter.py con el prompt")
            start_time = datetime.utcnow()
            output = subprocess.check_output(
                ['python3.11', 'prompter.py', user_query],
                stderr=subprocess.STDOUT,
                text=True
            )
            duration = (datetime.utcnow() - start_time).total_seconds()
            logger.debug("prompter.py completado en %.3f segundos", duration)

        except subprocess.CalledProcessError as e:
            logger.error("Error al ejecutar prompter.py", extra={"error": e.output})
            output = f"Error ejecutando prompter.py:\n{e.output}"

        return render_template('results.html', query=user_query, result=output)

    return render_template('index.html')

@main.route("/mapas")
def mapas():
    return render_template("mapas.html")

@main.route('/api/varieties', methods=['GET'])
def api_varieties():
    try:
        # Consulta con agregación de tipo 'terms' sobre el campo 'variety'
        res = client.search(index="vinos_a_uvas_enriched", body={
            "aggs": {
                "varieties_aggregation": {
                    "terms": {
                        "field": "variety",  # Cambiar 'variety' si el campo tiene un nombre diferente
                        "size": 1000,  # Ajusta el tamaño si es necesario
                        "order": { "_key": "asc" }
                    }
                }
            },
            "size": 0  # No necesitamos los documentos, solo las agregaciones
        })

        # Obtener las keys (nombres de las uvas) de la agregación
        varieties = [bucket["key"] for bucket in res['aggregations']['varieties_aggregation']['buckets']]
        
        # Si quieres también obtener el facetado con los valores, puedes incluir los counts
        varieties_with_count = [
            {"variety": bucket["key"], "count": bucket["doc_count"]}
            for bucket in res['aggregations']['varieties_aggregation']['buckets']
        ]
        
        # Devuelve tanto las keys como los valores para el facetado
        return jsonify({
            "varieties": varieties,
            "facetados": varieties_with_count
        })
        
    except Exception as e:
        logger.error("Error al consultar variedades: %s", e)
        return jsonify({"error": "Unable to fetch varieties"}), 500
    
@main.route("/api/mapdata", methods=["GET"])
def mapdata():
    wine_type = request.args.get("wine_type")
    if not wine_type:
        logger.error("Falta el parámetro 'wine_type' en la solicitud.")
        return jsonify({"error": "Missing wine_type parameter"}), 400

    query = {
        "size": 1000,
        "query": {
            "term": {
                "variety": wine_type
            }
        },
        "_source": ["province_geometry"]
    }

    try:
        logger.debug(f"Consultando Elasticsearch para obtener datos de 'province_geometry' para el tipo de vino: {wine_type}")
        res = client.search(index="vinos_a_uvas_enriched", body=query)
        features = []
        for hit in res["hits"]["hits"]:
            geom = hit["_source"].get("province_geometry")
            if geom:
                features.append({
                    "type": "Feature",
                    "geometry": geom,
                    "properties": {}
                })

        return jsonify({
            "type": "FeatureCollection",
            "features": features
        })

    except Exception as e:
        logger.error(f"Error al consultar Elasticsearch: {str(e)}")
        return jsonify({"error": str(e)}), 500

@main.route('/healthz', methods=['GET'])
def health_check():
    return jsonify({"status": "Application is running"})

def create_app():
    app = Flask(__name__)
    app.register_blueprint(main)
    print(f"Rutas registradas: {app.url_map}")
    return app
