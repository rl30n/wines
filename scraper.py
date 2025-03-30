from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
import time
import requests
import re
from datetime import datetime
import hashlib
from elasticsearch import Elasticsearch, helpers
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def parse_ficha(url, browser):
    page_obj = browser.new_page()
    page_obj.goto(url, timeout=30000)
    page_obj.wait_for_selector("h1")

    soup = BeautifulSoup(page_obj.content(), "lxml")
    print("✅ Página cargada correctamente.")
    
    print("🧾 HTML de la página:")
    print(soup.prettify())  # Imprime el HTML de la página cargada

    print("🔍 Buscando el nombre del vino...")
    name_elem = soup.select_one("div.contenido h1")
    winery_elem = soup.select_one("div.contenido h2")
    vino = {
        "url": url,
        "wine_name": name_elem.get_text(strip=True) if name_elem else None,
        "winery": winery_elem.get_text(strip=True) if winery_elem else None,
        "wine_description": None,
    }

    print("🔍 Buscando metadatos adicionales (apellation y tipo de vino)...")
    metadata = soup.select_one("div.metadatos")
    if metadata:
        appellation_elem = metadata.select_one("span.do a")
        if appellation_elem:
            vino["appellation"] = appellation_elem.get_text(strip=True)
            print("✅ Appellation:", vino["appellation"])
        type_elem = metadata.select_one("span.tipo")
        if type_elem:
            vino["wine_type"] = type_elem.get_text(strip=True)
            print("✅ Tipo de vino:", vino["wine_type"])
    else:
        print("⚠️ No se encontró la sección de metadatos.")

    print("🔍 Buscando la descripción del vino (h3 + p dentro de div.descripcion)...")
    descripcion_div = soup.select_one("div.descripcion")
    if descripcion_div:
        h3 = descripcion_div.select_one("h3")
        p = descripcion_div.select_one("p")
        desc_text = ""
        if h3:
            desc_text += h3.get_text(" ", strip=True) + " "
        if p:
            desc_text += p.get_text(" ", strip=True)
        vino["wine_description"] = desc_text.strip()
        print("✅ Descripción combinada:", vino["wine_description"])
    else:
        print("⚠️ No se encontró la sección de descripción.")

    print("🔍 Buscando perfil sensorial (Cata y Maridaje)...")
    sensory_div = soup.select_one("div#cata-y-maridaje")
    if sensory_div:
        sensory_profile = {}
        sections = {
            "cata_visual": "cata visual",
            "cata_olfativa": "cata olfativa",
            "cata_gustativa": "cata gustativa",
            "maridaje": "maridaje"
        }
        current = None
        for elem in sensory_div.children:
            if elem.name == "h4":
                key = next((k for k, v in sections.items() if v in elem.get_text(strip=True).lower()), None)
                if key:
                    current = key
            elif elem.name == "p" and current:
                sensory_profile[current] = elem.get_text(strip=True)
                current = None
        vino["sensory_profile"] = sensory_profile
        print("✅ Perfil sensorial:", sensory_profile)
    else:
        print("⚠️ No se encontró la sección de Cata y Maridaje.")

    print("🔍 Buscando vinification (elaboración)...")
    elaboracion_div = soup.select_one("div#elaboracion")
    if elaboracion_div:
        paragraphs = elaboracion_div.select("p")
        vino["vinification"] = " ".join(p.get_text(strip=True) for p in paragraphs)
        print("✅ Vinification:", vino["vinification"])
    else:
        print("⚠️ No se encontró la sección de Elaboración.")

    print("📋 Analizando la tabla lateral de características...")
    info_table = soup.select_one("div.col-xs-12.col-sm-12.col-md-4 > table.tabla-info-vino")
    if info_table:
        tabla_lateral = {}
        print("✅ Tabla lateral encontrada, procesando filas...")
        for row in info_table.find_all("tr"):
            header = row.find("th")
            value_cell = row.find("td")
            if not header or not value_cell:
                continue
            key = header.get_text(strip=True).lower()
            value_text = value_cell.get_text(" ", strip=True).strip()

            print(f"🔍 Fila de tabla detectada: '{key}' con valor '{value_text}'")

            if "d.o." in key or "igp" in key or "d.o./igp" in key:
                link = value_cell.find("a")
                tabla_lateral["appellation_table"] = link.get_text(strip=True) if link else value_text
            elif "provincia" in key:
                tabla_lateral["location_table"] = value_text
                # Obtener coordenadas aproximadas de la provincia con Nominatim
                try:
                    geocode_resp = requests.get("https://nominatim.openstreetmap.org/search", params={
                        "q": value_text + ", España",
                        "format": "json",
                        "limit": 1
                    }, headers={"User-Agent": "vino-scraper-bot"})
                    if geocode_resp.ok and geocode_resp.json():
                        loc_data = geocode_resp.json()[0]
                        tabla_lateral["location_coords"] = {
                            "lat": float(loc_data["lat"]),
                            "lon": float(loc_data["lon"])
                        }
                        print(f"🗺️ Coordenadas para '{value_text}': {tabla_lateral['location_coords']}")
                    else:
                        print(f"⚠️ No se encontraron coordenadas para '{value_text}'")
                except Exception as e:
                    print(f"❌ Error al buscar coordenadas para '{value_text}':", e)
            elif "variedades" in key:
                li_items = value_cell.select("li")
                tabla_lateral["variety_table"] = [li.get_text(strip=True) for li in li_items]
            elif "tipo de vino" in key:
                tabla_lateral["wine_type_table"] = value_text
            elif "crianza" in key:
                tabla_lateral["crianza_type"] = bool(value_cell.select_one("i.fas.fa-check-circle"))
            elif "barrica" in key:
                for li in value_cell.find_all("li"):
                    text = li.get_text(strip=True).lower()
                    if "tiempo" in text:
                        match = re.search(r"(\d+)", text)
                        if match:
                            tabla_lateral["barrel_time"] = int(match.group(1))
                    elif "tipo" in text:
                        subli = li.find("ul")
                        if subli:
                            tipo_li = subli.find("li")
                            if tipo_li:
                                tabla_lateral["barrel_type"] = tipo_li.get_text(strip=True)
            elif "grado alcohólico" in key:
                match = re.search(r"([\d\.]+)", value_text)
                tabla_lateral["grado"] = float(match.group(1)) if match else None
            elif "tª de servicio" in key:
                match = re.search(r"([\d\.]+)", value_text)
                tabla_lateral["temp_serv"] = float(match.group(1)) if match else None
            elif "tamaño" in key:
                match = re.search(r"([\d\.]+)", value_text)
                tabla_lateral["bottle_size"] = float(match.group(1)) if match else None

        vino["info_table"] = tabla_lateral
        print("📦 Datos de la tabla info_table añadidos al vino.")
        print(tabla_lateral)

        print("📦 Datos de la tabla extraídos:")
        for campo, valor in tabla_lateral.items():
            print(f"  {campo}: {valor}")

    print("🏅 Buscando premios...")
    premios_div = soup.select_one("div#premios")
    if premios_div:
        awards_dict = {}
        for row in premios_div.select("tr"):
            header = row.find("th")
            value_cell = row.find("td")
            if not header or not value_cell:
                continue
            key = header.get_text(strip=True).lower()
            value_text = value_cell.get_text(" ", strip=True).strip()
            awards_dict[key] = value_text if value_text else None
            print(f"🔍 Fila de tabla detectada: '{key}' con valor '{value_text}'")

        if not awards_dict:
            paragraphs = premios_div.find_all("p")
            texto_premios = " ".join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))
            if texto_premios:
                awards_dict["general"] = texto_premios

        vino["awards"] = awards_dict
        print("✅ Premios extraídos:", awards_dict)
    else:
        print("⚠️ No se encontró la sección de Premios.")

    print("💰 Buscando el precio de la botella...")
    precio_elem = soup.select_one("div.precioPorBotella span.precio")
    if precio_elem:
        match = re.search(r"(\d+[.,]?\d*)", precio_elem.get_text())
        if match:
            vino["bottle_price"] = float(match.group(1).replace(",", "."))
            print(f"✅ Precio por botella: {vino['bottle_price']}€")
        else:
            print("⚠️ No se pudo extraer el número del precio.")
    else:
        print("⚠️ No se encontró el elemento del precio.")

    # Añadir timestamp e ID único
    vino["@timestamp"] = datetime.utcnow().isoformat()
    unique_str = vino.get("url", "") + vino.get("wine_name", "")
    vino_id = hashlib.sha1(unique_str.encode("utf-8")).hexdigest()
    vino["_id"] = vino_id

    page_obj.close()
    return vino

def load_additional_wines():
    all_wines = []
    page = 1
    session = requests.Session()

    base_params = {
        'form': 'nombreVino=&variedadVino=0&tipoVino=&precioVino=0&doVino=&bodegaVino=&anadaVino=&premioTipo=&premioPuntuacion=&provincia=0&oferta=&ecologico=&pathCatalogoPage=%2Fvinos',
        'catalogo': '1',
        'tipoVino': ''
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://catatu.es/vinos"
    }

    while True:
        print(f"🔄 Cargando página AJAX {page}...")
        base_params["pg"] = page

        response = session.get("https://catatu.es/vinosAJAX", params=base_params, headers=headers)

        if response.ok:
            json_data = response.json()
            soup = BeautifulSoup(json_data['html'], "lxml")
            wine_elements = soup.select("div.nombre-vino a[href^='/vino/']")
            
            if not wine_elements:
                print("⚠️ No se encontraron más vinos en AJAX. Finalizando carga.")
                break

            for link in wine_elements:
                wine_url = "https://catatu.es" + link.get("href")
                if wine_url not in all_wines:
                    all_wines.append(wine_url)

            print(f"✅ Página {page} cargada: {len(wine_elements)} vinos encontrados. Total acumulado: {len(all_wines)}")
            page += 1
            time.sleep(1)
        else:
            print(f"❌ Error al cargar AJAX en página {page}: {response.status_code}")
            break

    return all_wines

if __name__ == "__main__":
    es = Elasticsearch("https://localhost:9200", basic_auth=("elastic", "changeme"), verify_certs=False)
    bulk_buffer = []
    bulk_size = 15
    last_sent_time = time.time()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=100)
        context = browser.new_context()
        print("🌐 Iniciando crawling en https://catatu.es/vinos/")
        
        # Cargar vinos adicionales
        additional_wine_urls = load_additional_wines()
        print(f"🔗 Se encontraron {len(additional_wine_urls)} vinos adicionales.")

        # Procesar vinos cargados
        for url in additional_wine_urls:
            print(f"\n🍷 Procesando vino: {url}")
            vino = parse_ficha(url, context)
            print(vino)

            # Prepare document for bulk indexing
            vino_to_index = dict(vino)
            vino_to_index.pop("_id", None)
            bulk_buffer.append({
                "_index": "vinos",
                "_id": vino["_id"],
                "_source": vino_to_index
            })

            # Check if we need to send the buffer or if we reached the bulk size
            if len(bulk_buffer) >= bulk_size or (time.time() - last_sent_time) >= 10:
                helpers.bulk(es, bulk_buffer)
                print(f"✅ Enviando {len(bulk_buffer)} documentos a Elasticsearch.")
                bulk_buffer.clear()
                last_sent_time = time.time()

        # Send any remaining documents in the buffer
        if bulk_buffer:
            helpers.bulk(es, bulk_buffer)
            print(f"✅ Enviando {len(bulk_buffer)} documentos restantes a Elasticsearch.")
        
        browser.close()