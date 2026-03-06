import json
import requests
from bs4 import BeautifulSoup
import time

# ==============================================
# Objetivo: 
#   - Abrir el JSON que ya contiene IDs y links de resoluciones
#   - Entrar a cada link de detalle de la resolución
#   - Extraer datos clave (fecha, entidad, expediente, primera instancia y link PDF)
#   - Guardar esos nuevos datos en el JSON
# ==============================================

# Nombre del archivo JSON original
JSON_FILE = "resolutions_data.json"

# Límite de resoluciones a procesar (ej: 15). 
# Si pones None, procesará todas.
LIMIT = None 

def extraer_datos(url):
    """
    Función que recibe la URL de la resolución
    y devuelve un diccionario con los datos extraídos.
    """
    try:
        # Descargar el HTML de la página
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        # ====== FECHA ======
        fecha_tag = soup.select_one("div.header.institution-document__header.black p:nth-of-type(2)")
        fecha = fecha_tag.get_text(strip=True) if fecha_tag else None

        # ====== ENTIDAD (Reclamado:) ======
        entidad_tag = soup.select_one("div.description.rule-content div:nth-of-type(1)")
        if entidad_tag:
            strong = entidad_tag.find("strong")
            entidad = strong.next_sibling.strip() if strong and strong.next_sibling else None
        else:
            entidad = None

        # ====== NÚMERO DE EXPEDIENTE ======
        expediente_tag = soup.select_one("div.description.rule-content div:nth-of-type(2)")
        if expediente_tag:
            texto = expediente_tag.get_text(strip=True)
            expediente= texto.split(":", 1)[1].strip() if ":" in texto else texto
        else:
            expediente = None


        # ====== RESOLUCIÓN DE PRIMERA INSTANCIA ======
        primera_instancia_tag = soup.select_one("div.description.rule-content div:nth-of-type(5)")
        primera_instancia = primera_instancia_tag.get_text(strip=True) if primera_instancia_tag else None

        # ====== LINK DE RESOLUCIÓN (PDF) ======
        pdf_tag = soup.select_one("a.download[href]")
        link_resolucion = pdf_tag["href"] if pdf_tag else None

        return {
            "fecha": fecha,
            "entidad": entidad,
            "expediente": expediente,
            "resolucion_primera_instancia": primera_instancia,
            "link_resolucion": link_resolucion
        }

    except Exception as e:
        print(f"❌ Error al procesar {url}: {e}")
        return None


def main():
    # 1. Abrir el JSON que ya tenemos
    with open(JSON_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 2. Recorrer cada resolución
    for idx, resol in enumerate(data):
        if LIMIT and idx >= LIMIT:
            print(f"⏭ Se alcanzó el límite de {LIMIT} resoluciones.")
            break

        url = resol.get("detalle_url")
        if not url:
            continue
        
        print(f"🔎 Procesando ID {resol['id']} -> {url}")
        datos_extraidos = extraer_datos(url)

        # 3. Agregar los datos extraídos al JSON si la extracción fue exitosa
        if datos_extraidos:
            resol.update(datos_extraidos)
            print(f"✅ Datos extraídos: {datos_extraidos}")
        else:
            print(f"⚠️ No se pudo extraer datos para ID {resol['id']}")

        # Pequeña pausa entre requests (evita bloqueos)
        time.sleep(1)

    # 4. Guardar el JSON actualizado
    with open("resolutions_data2.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

    print("💾 JSON enriquecido guardado")


if __name__ == "__main__":
    main()
