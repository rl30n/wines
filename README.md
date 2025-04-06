# 🥂 Wines Project

Este proyecto permite realizar scraping, enriquecimiento semántico y consultas inteligentes sobre un conjunto de datos de vinos usando Python, Elasticsearch y un modelo de lenguaje (Mistral) local.

## 📁 Estructura del proyecto

- `scraper.py`: Extrae y normaliza datos de diferentes fuentes (HTML, CSV, JSON).
- `enrichment.py`: Genera embeddings de texto con un modelo local (Mistral) y actualiza documentos en Elasticsearch usando escritura por lotes (`bulk`).
- `prompter.py`: CLI para consultar el índice en modo RAG (Retrieval-Augmented Generation) contra los embeddings almacenados.

## 🐍 Configuración del entorno virtual

Se recomienda usar Python 3.11+.

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 🔧 Requisitos

- Elasticsearch 8.17.4 corriendo en `https://localhost:9200` con usuario `elastic` y contraseña (configurable).
- Mistral funcionando localmente como API REST en `http://localhost:11434` compatible con `ollama`.
- Python 3.11 o superior.
- Dependencias listadas en `requirements.txt`.

## ⚙️ Uso

### Scraper

Ejecuta:

```bash
python scraper.py
```

Esto genera los documentos base para indexar, extraídos y normalizados desde las fuentes originales.

```bash
python scraper.py --debug
```

Esto activa el nivel de log `DEBUG` (formato ECS) y guarda también los logs en `logs/scraper.log` con rotación diaria y retención de 7 días.


### Enrichment

Ejecución normal:

```bash
python enrichment.py 
```

Ejecuta con opción de logging:

```bash
python enrichment.py --debug
```

Esto activa el nivel de log `DEBUG` (formato ECS) y guarda también los logs en `logs/enrichment.log` con rotación diaria y retención de 7 días.

Esto añade el campo `combined_text_embedding` a cada documento en el índice `vinos_embeddings`.

### Prompter

Realiza una consulta:

```bash
python prompter.py "Quiero un vino afrutado para acompañar sushi" --debug
```

Realiza una consulta en debug:

```bash
python prompter.py "Quiero un vino afrutado para acompañar sushi" --debug
```

Esto genera un embedding para el prompt y consulta el índice con búsqueda por vectores (`knn`) sobre el campo `combined_text_embedding`.

## 📌 Notas

- El campo `combined_text_embedding` debe tener `dims: 384` en el template de índice.
- Se usa `ecs-logging` para salida estructurada en consola y en archivo `logs/prompter.log`.

---
