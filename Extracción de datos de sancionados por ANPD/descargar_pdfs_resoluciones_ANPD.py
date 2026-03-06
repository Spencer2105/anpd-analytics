import json
import requests
import time
import os

# Archivos auxiliares
json_file = "resolutions_data.json"
last_id_file = "ultimo_id.txt"
failed_ids_file = "ids_fallidos.txt"

# Carpeta de salida (ya creada por ti)
carpeta_salida = r"G:\Mi unidad\Resoluciones ANPD\PDFs"

os.makedirs(carpeta_salida, exist_ok=True)

# Cargar JSON
with open(json_file, "r", encoding="utf-8") as f:
    data = json.load(f)

# Verificar desde qué ID empezar
start_id = 1
if os.path.exists(last_id_file):
    with open(last_id_file, "r") as f:
        start_id = int(f.read().strip())

print(f"🔄 Reanudando desde ID {start_id}")

# Función para validar si un PDF es válido
def pdf_valido(path):
    try:
        if os.path.getsize(path) < 50 * 1024:  # mínimo 50 KB
            return False
        with open(path, "rb") as f:
            header = f.read(5)
            return header == b"%PDF-"
    except Exception:
        return False

# Descargar PDFs
for i, resolucion in enumerate(data, start=1):
    if i < start_id:
        continue  # omitir IDs ya descargados

    url = resolucion.get("link_resolucion")
    nombre_base = resolucion.get("resolución_primera_instancia", f"resolucion_{i}")
    nombre_limpio = "".join(c for c in nombre_base if c.isalnum() or c in (" ", "_", "-")).rstrip()
    nombre_archivo = os.path.join(carpeta_salida, f"{i:03d}_{nombre_limpio}.pdf")

    intentos = 0
    exito = False

    while intentos < 3 and not exito:
        try:
            print(f"⬇️ Descargando {i}/{len(data)}: {url} (intento {intentos+1})")
            r = requests.get(url, timeout=30)
            r.raise_for_status()

            with open(nombre_archivo, "wb") as f:
                f.write(r.content)

            if pdf_valido(nombre_archivo):
                print(f"✅ Guardado como {nombre_archivo}")
                exito = True
            else:
                print(f"⚠️ Archivo inválido ({os.path.getsize(nombre_archivo)} bytes). Reintentando...")
                os.remove(nombre_archivo)

        except Exception as e:
            print(f"❌ Error en {i}: {e}")

        intentos += 1
        if not exito:
            time.sleep(5)

    if not exito:
        print(f"🚨 Falló definitivamente el ID {i}. Guardando en {failed_ids_file}")
        with open(failed_ids_file, "a") as f:
            f.write(f"{i}\n")

    # Guardar progreso en caso de interrupción
    with open(last_id_file, "w") as f:
        f.write(str(i + 1))

    time.sleep(5)  # espera entre descargas

# Si terminó todo correctamente, borrar el archivo de progreso
if os.path.exists(last_id_file):
    os.remove(last_id_file)
    print("🎉 Todas las descargas completadas. Progreso reseteado.")
