from flask import Blueprint, render_template, request
import subprocess
import json

main = Blueprint('main', __name__)

@main.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        user_query = request.form['query']

        # Ejecutar prompter.py y capturar su salida
        try:
            output = subprocess.check_output(
                ['python3.11', 'prompter.py', user_query],
                stderr=subprocess.STDOUT,
                text=True
            )
        except subprocess.CalledProcessError as e:
            output = f"Error ejecutando prompter.py:\n{e.output}"

        return render_template('results.html', query=user_query, result=output)

    return render_template('index.html')