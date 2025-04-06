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

        try:
            output = subprocess.check_output(
                ['python3.11', 'prompter.py', combined_query],
                stderr=subprocess.STDOUT,
                text=True
            )
        except subprocess.CalledProcessError as e:
            output = f"Error ejecutando prompter.py:\n{e.output}"

        return render_template('results.html', query=user_query, result=output, context=combined_query)

    return render_template('index.html')