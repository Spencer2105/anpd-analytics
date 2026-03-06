# Antes de todo se deben instalar las librerías necesarias:
# pip install requests
# pip install beautifulsoup4

import requests
from bs4 import BeautifulSoup
import json
import time

# ==============================
# CONFIGURACIÓN GENERAL
# ==============================
BASE_URL = "https://www.gob.pe/institucion/anpd/colecciones/1801-resoluciones-de-los-procedimientos-sancionadores"
TOTAL_PAGES = 9  # Número de páginas a scrapear (lo puedes cambiar fácilmente)
MAX_RETRIES = 5  # Máximos intentos en caso de error al cargar la página
WAIT_SECONDS = 3  # Tiempo de espera base entre reintentos
OUTPUT_FILE = "resolutions_data1.json"  # Archivo de salida (JSON)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-PE,es;q=0.9",
}

# ==============================
# FUNCIÓN PARA DESCARGAR UNA PÁGINA CON REINTENTOS
# ==============================
def get_page_content(url):
    """
    Descarga el contenido HTML de una página con reintentos automáticos
    si ocurre un error de conexión o timeout.
    """
    for intento in range(1, MAX_RETRIES + 2):
        try:
            response = requests.get(url, headers=HEADERS, timeout=10)
            response.raise_for_status()  # Lanza error si el status != 200
            return response.text
        except Exception as e:
            print(f"[ERROR] Falló el intento {intento} para {url}: {e}")
            if intento < MAX_RETRIES:
                wait_time = WAIT_SECONDS * intento  # aumenta el tiempo de espera progresivamente
                print(f"Reintentando en {wait_time} segundos...")
                time.sleep(wait_time)
            else:
                print(f"[AVISO] No se pudo acceder a {url} tras {MAX_RETRIES} intentos. Saltando...")
                return None

# ==============================
# FUNCIÓN PRINCIPAL DE SCRAPING
# ==============================
def scrape_resoluciones():
    """
    Recorre todas las páginas de resoluciones, extrae los links hacia 
    el detalle de cada resolución y los guarda en un archivo JSON.
    """
    resultados = []
    id = 1
    for page in range(1, TOTAL_PAGES + 1):
        print(f"\n=== Procesando página {page}/{TOTAL_PAGES} ===")

        url = (
            f"{BASE_URL}?filter%5Bend_date%5D=&filter%5Border%5D=publication_desc"
            f"&filter%5Bper_page%5D=100&filter%5Bstart_date%5D=&filter%5Bterms%5D=&sheet={page}"
        )

        html = get_page_content(url)
        if not html:
            continue

        soup = BeautifulSoup(html, "html.parser")
        links = soup.find_all("a", class_="leading-6 font-bold")

        for link in links:
            id = id + 1
            titulo = link.text.strip()
            href = link["href"]
            full_url = "https://www.gob.pe" + href
            resultados.append({
                "id": id,
                "titulo": titulo,
                "detalle_url": full_url
            })

        print(f"   → Se extrajeron {len(links)} links en esta página.")
        time.sleep(1)  # pausa entre páginas para evitar bloqueos

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(resultados, f, indent=4, ensure_ascii=False)

    print(f"\n✅ Proceso completado. Se extrajeron {len(resultados)} resoluciones.")
    print(f"   Archivo guardado en: {OUTPUT_FILE}")

# ==============================
# EJECUCIÓN
# ==============================
if __name__ == "__main__":
    scrape_resoluciones()