from flask import Flask, render_template, request, Blueprint
import subprocess
import json
import argparse
import logging
import ecs_logging
import sys
from datetime import datetime
import os

# Configurar logger ECS
logger = logging.getLogger("vinosearch")
logger.setLevel(logging.INFO)

log_directory = "logs"
os.makedirs(log_directory, exist_ok=True)
log_file_path = os.path.join(log_directory, "webapp.log")

file_handler = logging.FileHandler(log_file_path)
file_handler.setFormatter(ecs_logging.StdlibFormatter())
logger.addHandler(file_handler)

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(ecs_logging.StdlibFormatter())
logger.addHandler(console_handler)

# Parser para modo debug
parser = argparse.ArgumentParser(description="Aplicación Flask con ECS logging")
parser.add_argument("--debug", action="store_true", help="Activa modo debug")
args, unknown = parser.parse_known_args()

if args.debug:
    logger.setLevel(logging.DEBUG)
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

def create_app():
    app = Flask(__name__)
    app.register_blueprint(main)
    return app
