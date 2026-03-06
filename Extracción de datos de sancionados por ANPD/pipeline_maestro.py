"""
SCRAPER UNIFICADO - ANPD
=========================
Paso 1: Scrapea todos los links de resoluciones
Paso 2: Entra a cada link y extrae fecha, entidad, expediente, link PDF
Todo en un solo archivo JSON final.

Uso: python scraper_unificado.py
"""

import requests
from bs4 import BeautifulSoup
import json
import time
import os

# ─── CONFIGURACIÓN ────────────────────────────────────────────────────────────
BASE_URL     = "https://www.gob.pe/institucion/anpd/colecciones/1801-resoluciones-de-los-procedimientos-sancionadores"
TOTAL_PAGES  = 9
MAX_RETRIES  = 5
WAIT_SECONDS = 3
OUTPUT_FILE  = "resolutions_data.json"   # archivo final con todo
PROGRESO_FILE = "scraper_progreso.json"  # para retomar si se interrumpe

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-PE,es;q=0.9",
}

# ─── UTILIDADES ───────────────────────────────────────────────────────────────

def get_page_content(url):
    """Descarga HTML con reintentos y headers para evitar bloqueos."""
    for intento in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(url, headers=HEADERS, timeout=10)
            response.raise_for_status()
            return response.text
        except Exception as e:
            print(f"  [ERROR] Intento {intento} fallido: {e}")
            if intento < MAX_RETRIES:
                wait = WAIT_SECONDS * intento
                print(f"  Reintentando en {wait}s...")
                time.sleep(wait)
    print(f"  [AVISO] No se pudo acceder tras {MAX_RETRIES} intentos. Saltando.")
    return None

def cargar_progreso():
    """Carga el progreso guardado para retomar si se interrumpe."""
    if os.path.exists(PROGRESO_FILE):
        with open(PROGRESO_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"urls_procesadas": []}

def guardar_progreso(progreso):
    with open(PROGRESO_FILE, "w", encoding="utf-8") as f:
        json.dump(progreso, f, ensure_ascii=False)

# ─── PASO 1: SCRAPING DE LINKS ────────────────────────────────────────────────

def scrape_links():
    """Recorre todas las páginas y extrae los links de resoluciones."""
    print("\n" + "="*55)
    print("  PASO 1: Scraping de links de resoluciones")
    print("="*55)

    # Cargar resoluciones existentes para no duplicar
    existentes = []
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            existentes = json.load(f)
    
    urls_existentes = {item["detalle_url"] for item in existentes}
    id_counter = max((item["id"] for item in existentes), default=0) + 1

    nuevas = []
    for page in range(1, TOTAL_PAGES + 1):
        print(f"\n  Página {page}/{TOTAL_PAGES}...")

        url = (
            f"{BASE_URL}?filter%5Bend_date%5D=&filter%5Border%5D=publication_desc"
            f"&filter%5Bper_page%5D=100&filter%5Bstart_date%5D=&filter%5Bterms%5D=&sheet={page}"
        )

        html = get_page_content(url)
        if not html:
            continue

        soup = BeautifulSoup(html, "html.parser")
        links = soup.find_all("a", class_="leading-6 font-bold")

        encontradas_pag = 0
        for link in links:
            titulo   = link.text.strip()
            href     = link["href"]
            full_url = "https://www.gob.pe" + href

            if full_url in urls_existentes:
                continue  # ya existe, saltar

            nuevas.append({
                "id":          id_counter,
                "titulo":      titulo,
                "detalle_url": full_url,
                # campos que se llenan en el paso 2:
                "fecha":                        None,
                "entidad":                      None,
                "expediente":                   None,
                "resolucion_primera_instancia": None,
                "link_resolucion":              None,
            })
            urls_existentes.add(full_url)
            id_counter += 1
            encontradas_pag += 1

        print(f"  → {encontradas_pag} nuevas encontradas en esta página.")
        time.sleep(1)

    total = len(existentes) + len(nuevas)
    print(f"\n  ✅ Paso 1 completo: {len(nuevas)} nuevas | {total} total")
    return existentes + nuevas

# ─── PASO 2: ENRIQUECIMIENTO CON DATOS DE DETALLE ────────────────────────────

def extraer_datos_detalle(url):
    """Extrae fecha, entidad, expediente y link PDF de la página de detalle."""
    html = get_page_content(url)
    if not html:
        return None

    soup = BeautifulSoup(html, "html.parser")

    # Fecha
    fecha_tag = soup.select_one("div.header.institution-document__header.black p:nth-of-type(2)")
    fecha = fecha_tag.get_text(strip=True) if fecha_tag else None

    # Entidad
    entidad_tag = soup.select_one("div.description.rule-content div:nth-of-type(1)")
    entidad = None
    if entidad_tag:
        strong = entidad_tag.find("strong")
        entidad = strong.next_sibling.strip() if strong and strong.next_sibling else None

    # Expediente
    expediente_tag = soup.select_one("div.description.rule-content div:nth-of-type(2)")
    expediente = None
    if expediente_tag:
        texto = expediente_tag.get_text(strip=True)
        expediente = texto.split(":", 1)[1].strip() if ":" in texto else texto

    # Resolución primera instancia
    primera_tag = soup.select_one("div.description.rule-content div:nth-of-type(5)")
    primera = primera_tag.get_text(strip=True) if primera_tag else None

    # Link PDF
    pdf_tag = soup.select_one("a.download[href]")
    link_pdf = pdf_tag["href"] if pdf_tag else None

    return {
        "fecha":                        fecha,
        "entidad":                      entidad,
        "expediente":                   expediente,
        "resolucion_primera_instancia": primera,
        "link_resolucion":              link_pdf,
    }

def enriquecer_datos(data):
    """Entra a cada página de detalle y completa los campos faltantes."""
    print("\n" + "="*55)
    print("  PASO 2: Enriquecimiento con datos de detalle")
    print("="*55)

    progreso = cargar_progreso()
    urls_procesadas = set(progreso["urls_procesadas"])

    pendientes = [
        item for item in data
        if item["detalle_url"] not in urls_procesadas and item.get("fecha") is None
    ]

    print(f"  {len(pendientes)} resoluciones pendientes de enriquecer.")

    for i, item in enumerate(pendientes):
        url = item["detalle_url"]
        print(f"  [{i+1}/{len(pendientes)}] ID {item['id']} → {item['titulo'][:50]}...", end=" ")

        detalles = extraer_datos_detalle(url)
        if detalles:
            item.update(detalles)
            print("✅")
        else:
            print("❌ sin datos")

        urls_procesadas.add(url)

        # Guardar progreso cada 10 resoluciones
        if (i + 1) % 10 == 0:
            guardar_progreso({"urls_procesadas": list(urls_procesadas)})
            with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"\n  💾 Progreso guardado ({i+1} procesadas)\n")

        time.sleep(1)

    # Guardado final
    guardar_progreso({"urls_procesadas": list(urls_procesadas)})
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n  ✅ Paso 2 completo. JSON guardado en {OUTPUT_FILE}")
    return data

# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    print("\n SCRAPER UNIFICADO ANPD")
    print(f"   Output: {OUTPUT_FILE}")

    # Paso 1: obtener todos los links
    data = scrape_links()

    # Paso 2: enriquecer con datos de detalle
    data = enriquecer_datos(data)

    print(f"\n Proceso completo. {len(data)} resoluciones en {OUTPUT_FILE}")

if __name__ == "__main__":
    main()