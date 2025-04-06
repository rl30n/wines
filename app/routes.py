from flask import Blueprint, render_template, request, jsonify
import subprocess
import json
from elasticsearch import Elasticsearch
import ecs_logging
import logging
import sys

# Configuración del logger con ECS
logger = logging.getLogger(__name__)
handler = logging.StreamHandler(sys.stdout)
formatter = ecs_logging.StdlibFormatter()
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.DEBUG if '--debug' in sys.argv else logging.INFO)

main = Blueprint('main', __name__)

@main.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        user_query = request.form['query']

        logger.debug(f"Recibiendo consulta del usuario: {user_query}")

        # Ejecutar prompter.py y capturar su salida
        try:
            logger.debug("Ejecutando prompter.py con la consulta del usuario.")
            output = subprocess.check_output(
                ['python3.11', 'prompter.py', user_query],
                stderr=subprocess.STDOUT,
                text=True
            )
            logger.debug(f"Salida de prompter.py: {output}")

        except subprocess.CalledProcessError as e:
            logger.error(f"Error ejecutando prompter.py: {e.output}")
            output = f"Error ejecutando prompter.py:\n{e.output}"

        return render_template('results.html', query=user_query, result=output)

    return render_template('index.html')

@main.route('/ask', methods=['GET', 'POST'])
def ask():
    if request.method == 'POST':
        user_query = request.form['query']
        include_context = request.form.get('include_context')
        previous_context = request.form.get('context', '') if include_context else ''

        # Combinar contexto previo si existe
        if previous_context:
            combined_query = f"{previous_context}\n{user_query}"
        else:
            combined_query = user_query

        logger.debug(f"Consulta combinada: {combined_query}")

        try:
            logger.debug("Ejecutando prompter.py con contexto y consulta combinada.")
            output = subprocess.check_output(
                ['python3.11', 'prompter.py', combined_query],
                stderr=subprocess.STDOUT,
                text=True
            )
            logger.debug(f"Salida de prompter.py con contexto: {output}")

        except subprocess.CalledProcessError as e:
            logger.error(f"Error ejecutando prompter.py: {e.output}")
            output = f"Error ejecutando prompter.py:\n{e.output}"

        return render_template('results.html', query=user_query, result=output, context=combined_query)

    return render_template('index.html')

@main.route("/mapas")
def mapas():
    logger.debug("Accediendo a la página de mapas.")
    return render_template("mapas.html")

es = Elasticsearch("https://localhost:9200", verify_certs=False)




    
