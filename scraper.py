from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
import time
import requests

BASE_URL = "https://www.vinetur.com/vinos/page/{}/"

def get_page_html_with_requests_session(playwright, url):
    browser = playwright.chromium.launch(headless=False, slow_mo=100)
    context = browser.new_context()
    page = context.new_page()
    page.goto(url, timeout=30000)
    page.wait_for_timeout(3000)  # Deja que cargue cookies y JS

    # Extrae cookies y user-agent
    cookies = context.cookies()
    ua = page.evaluate("() => navigator.userAgent")

    # Cierra navegador
    browser.close()

    # Convierte cookies para requests
    session_cookies = {cookie["name"]: cookie["value"] for cookie in cookies}
    headers = {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "es-ES,es;q=0.9",
        "Connection": "keep-alive",
    }

    response = requests.get(url, headers=headers, cookies=session_cookies)
    print(f"🌐 Código de respuesta: {response.status_code}")
    return response.text

def get_ficha_links(page, browser):
    url = BASE_URL.format(page)
    page_obj = browser.new_page()
    page_obj.goto(url, timeout=30000)

    try:
        page_obj.wait_for_selector("article", timeout=10000)
    except:
        print(f"⚠️ No se encontró contenido en la página {page}")
        print(page_obj.content()[:1000])  # Fragmento del HTML para debugging
        page_obj.close()
        return []

    soup = BeautifulSoup(page_obj.content(), "lxml")
    links = []
    for article in soup.select("article"):
        a = article.find("a")
        if a and a["href"].startswith("https://www.vinetur.com/vinos/"):
            links.append(a["href"])

    print(f"🔗 Encontrados {len(links)} links en página {page}")
    page_obj.close()
    return links

def parse_ficha(url, browser):
    page_obj = browser.new_page()
    page_obj.goto(url, timeout=30000)
    page_obj.wait_for_selector("h1")

    soup = BeautifulSoup(page_obj.content(), "lxml")
    vino = {}
    vino["url"] = url

    h1 = soup.find("h1")
    vino["nombre"] = h1.text.strip() if h1 else "Desconocido"

    info_box = soup.find("ul", class_="datos-vino")
    if info_box:
        for li in info_box.find_all("li"):
            label = li.find("strong")
            if label:
                key = label.text.strip().lower().replace(":", "")
                value = label.next_sibling.strip() if label.next_sibling else ""
                vino[key] = value

    descripcion = soup.find("div", class_="descripcion")
    if descripcion:
        vino["descripcion"] = descripcion.text.strip()

    page_obj.close()
    return vino

def scrape_vinos(max_pages=3, delay=1.5):
    all_vinos = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=100)
        context = browser.new_context()
        for page in range(1, max_pages + 1):
            print(f"📄 Página {page}")
            links = get_ficha_links(page, context)
            for link in links:
                print(f" → Scrapeando: {link}")
                vino = parse_ficha(link, context)
                all_vinos.append(vino)
                time.sleep(delay)
        browser.close()
    return all_vinos

if __name__ == "__main__":
    with sync_playwright() as p:
        html = get_page_html_with_requests_session(p, "https://www.vinetur.com/vinos/page/1/")
        print(html[:2000])  # Muestra un fragmento del HTML obtenido con requests
    # vinos = scrape_vinos(max_pages=2)
    for v in vinos:
        print(v)