import os
import shutil
import pandas as pd
import obtener_data as od

archivo_json="resolutions_data.json"
carpeta_base= r"G:\Mi unidad\Resoluciones ANPD\PDFs"

def organizar_pdfs(df, carpeta_base):
    """
    Organiza los PDFs en carpetas por año según el DataFrame.
    
    Args:
        df (pd.DataFrame): DataFrame con columnas ['id', 'year_resolucion'] al menos.
        carpeta_base (str): Carpeta donde están los PDFs.
    """
    for archivo in os.listdir(carpeta_base):
        if not archivo.lower().endswith(".pdf"):
            continue  # ignorar si no es PDF

        ruta_actual = os.path.join(carpeta_base, archivo)

        # Obtener ID con la nueva función
        id_int = od.obtener_id_desde_archivo(archivo)
        if id_int is None:
            continue

        # Buscar el año en el DataFrame
        fila = df[df["id"] == id_int]
        if fila.empty:
            print(f"⚠️ ID {id_int} no encontrado en el DataFrame ({archivo})")
            continue

        year_resolucion = str(fila.iloc[0]["year_resolucion"])

        # Crear carpeta destino
        carpeta_destino = os.path.join(carpeta_base, year_resolucion)
        os.makedirs(carpeta_destino, exist_ok=True)

        # Mover el archivo
        ruta_destino = os.path.join(carpeta_destino, archivo)
        shutil.move(ruta_actual, ruta_destino)
        print(f"✅ Movido {archivo} → {carpeta_destino}")

df=od.crear_year_resolucion(od.json_a_df(archivo_json))
organizar_pdfs(df,carpeta_base)