from lector_pdfs import extraer_texto_pdf
import pandas as pd
from pathlib import Path
import os
from lector_pdfs import LectorPDF
import re
import json
from rag_multas_system import RAGMultasProcessor

archivo_json="resolutions_data.json"
carpeta_pdfs=r"G:\Mi unidad\Resoluciones ANPD\PDFs\2024"

ruta=r"G:\Mi unidad\Resoluciones ANPD\PDFs\2025\003_resolucion_3.pdf"


def json_a_df(archivo_json):
    df=pd.read_json(archivo_json)
    # Filtrar columnas
    df = df[["id", "titulo", "detalle_url","fecha","entidad","link_resolucion"]]

    # Renombrar columnas
    df = df.rename(columns={
        "entidad": "entidad_sancionada"
    })
    return df

def crear_year_resolucion(df):
    df["year_resolucion"]=df["fecha"].str[-4:]
    return df

def obtener_year_resoluciones(df,id):
    resultado = df.loc[df["id"] == id, "year_resolucion"].values[0]
    return resultado

def obtener_fecha_resoluciones(df,id):
    resultado = df.loc[df["id"] == id, "fecha"].values[0]
    return resultado

def obtener_entidad_resoluciones(df,id):
    resultado = df.loc[df["id"] == id, "entidad_sancionada"].values[0]
    return resultado

def obtener_titulo_resoluciones(df,id):
    resultado = df.loc[df["id"] == id, "titulo"].values[0]
    return resultado

def obtener_detalle_url_resoluciones(df,id):
    resultado = df.loc[df["id"] == id, "detalle_url"].values[0]
    return resultado

def obtener_link_pdf_resoluciones(df,id):
    resultado = df.loc[df["id"] == id, "link_resolucion"].values[0]
    return resultado


def obtener_id_desde_archivo(nombre_archivo: str):
    """
    Extrae y valida el ID desde el nombre del archivo PDF.

    Args:
        nombre_archivo (str): Nombre del archivo (ejemplo: '000123_resolucion.pdf').

    Returns:
        int | None: El ID como entero si es válido, o None si no se pudo extraer.
    """
    # Validar si tiene "_"
    if "_" not in nombre_archivo:
        print(f"⚠️ El archivo {nombre_archivo} no tiene '_' ")
        return None

    # Extraer ID (parte antes del "_")
    id_str = nombre_archivo.split("_")[0]

    # Quitar ceros iniciales
    id_str = id_str.lstrip("0")

    if not id_str:  # si quedó vacío
        print(f"⚠️ No se pudo obtener ID de {nombre_archivo}")
        return None

    try:
        return int(id_str)
    except ValueError:
        print(f"⚠️ ID inválido en {nombre_archivo}")
        return None


    

def procesar_pdfs_en_carpeta(carpeta_pdf: str, archivo_salida_json: str):
    resultados = []
    df=json_a_df("resolutions_data.json")

    for archivo in os.listdir(carpeta_pdf):
        if archivo.lower().endswith(".pdf"):
            ruta_pdf = os.path.join(carpeta_pdf, archivo)
            id_archivo = os.path.splitext(archivo)[0]  # nombre sin extensión
            df=crear_year_resolucion(df)



            id=obtener_id_desde_archivo(id_archivo)
            titulo=obtener_titulo_resoluciones(df,id)
            detalle_url=obtener_detalle_url_resoluciones(df,id)
            link_pdf=obtener_link_pdf_resoluciones(df,id)
            entidad_sancionada=obtener_entidad_resoluciones(df,id)
            year_resolucion=obtener_year_resoluciones(df,id)
            fecha=obtener_fecha_resoluciones(df,id)
            

            # Llamar a tu método
            resolucion_directoral,conceptos_infracciones, articulos_conceptos_infracciones, tipo_infraccion, ley_tipo_infraccion, multas = obtener_datos_pdf_2025(ruta_pdf)

            # Crear el diccionario base
            registro = {"id": id,"titulo":titulo,"resolucion_directoral":resolucion_directoral,"detalle_url":detalle_url,"link_pdf":link_pdf,"entidad_sancionada":entidad_sancionada,"year_resolucion":year_resolucion,"fecha":fecha, "conceptos_infracciones": conceptos_infracciones,}

            # Expandir listas numeradas
            for i, valor in enumerate(articulos_conceptos_infracciones, start=1):
                registro[f"articulos_conceptos_infracciones{i}"] = valor

            for i, valor in enumerate(tipo_infraccion, start=1):
                registro[f"tipo_infraccion{i}"] = valor

            for i, valor in enumerate(ley_tipo_infraccion, start=1):
                registro[f"ley_tipo_infraccion{i}"] = valor

            for i, valor in enumerate(multas, start=1):
                registro[f"multas{i}"] = valor

            # Agregar a la lista de resultados
            resultados.append(registro)
            print(f"Datos capturados del archivo {id}")

    # Guardar todo en un archivo JSON
    with open(archivo_salida_json, "w", encoding="utf-8") as f:
        json.dump(resultados, f, ensure_ascii=False, indent=4)

    print(f"✅ Resultados guardados en {archivo_salida_json}")

def eliminar_tablas(texto: str) -> str:
    """
    Elimina todas las tablas delimitadas por [TABLA ...] y [FIN TABLA]
    incluyendo todos los saltos de línea que haya dentro.
    """
    # Patrón: desde [TABLA ...] hasta [FIN TABLA], modo DOTALL para incluir saltos de línea
    patron_tabla = r'\[TABLA.*?\].*?\[FIN TABLA\]'
    texto_limpio = re.sub(patron_tabla, '', texto, flags=re.DOTALL | re.IGNORECASE)
    
    # Eliminar saltos de línea múltiples que hayan quedado
    texto_limpio = re.sub(r'\n{2,}', '\n', texto_limpio)
    return texto_limpio.strip()

def quitar_saltos_lineas(texto):
    """
    Elimina saltos de línea (\n) y espacios extra.
    - Si recibe un string, devuelve un string limpio.
    - Si recibe una lista de strings, devuelve una lista con cada string limpio.
    """
    if isinstance(texto, str):
        return texto.replace("\n", " ").strip()
    elif isinstance(texto, list):
        return [p.replace("\n", " ").strip() for p in texto]
    else:
        raise TypeError("Se esperaba un string o una lista de strings")

def obtener_conceptos_infracciones(texto_detalle_sanciones):
    """
    Extrae el texto del concepto de sanciones desde la frase
    'se ha establecido la responsabilidad de la administrada por'
    hasta antes de un número seguido de punto (ej. 131.).
    Además, elimina cualquier ocurrencia de '===Fin de la página N==='
    """
    patron_concepto_sanciones = (
        r"(?:se ha establecido la responsabilidad de la administrada por"
        r"|se ha establecido la responsabilidad sancionable por)"
        r"(.*?)"
        r"(?=\n?\s*\d+\.(?!\d))"
    )

    m = re.search(patron_concepto_sanciones, texto_detalle_sanciones, re.IGNORECASE | re.DOTALL)
    if m:
        texto_extraido = m.group(1).strip()
        # Eliminar los separadores de fin de página
        texto_limpio = re.sub(r'===Fin de la página \d+===', '', texto_extraido)
        # También podemos limpiar espacios extra
        texto_limpio = texto_limpio.strip()
        return texto_limpio

    return "Conceptos no encontrados"

def obtener_articulos_conceptos_infracciones(texto: str) -> list:
    """
    Busca coincidencias de 'articulo' o 'artículo' (mayus/minus, con o sin tilde)
    y extrae la frase hasta encontrar coma, punto y coma o punto.
    Devuelve una lista de coincidencias.
    """
    patron_articulos_conceptos_infracciones = r"(art[ií]culo.*?)(?=[,;.]\s| y\s|$)"
    coincidencias = re.findall(patron_articulos_conceptos_infracciones, texto, flags=re.IGNORECASE)
    return [m.strip() for m in coincidencias if re.search(r"\d+", m)]
    

def obtener_datos_pdf_2025(ruta_archivo):
    lector = LectorPDF(ruta_archivo)
    paginas_finales = lector.contar_paginas()
    const=paginas_finales*0.36

    texto_pag_finales, estadisticas = extraer_texto_pdf(ruta_archivo, paginas_finales-int(const), paginas_finales)

    resolucion_directoral=obtener_resolucion_directoral(texto_pag_finales)

    texto_pag_finales=eliminar_primera_linea_por_pagina(texto_pag_finales)
    texto_pag_finales=eliminar_tablas(texto_pag_finales)

    # Definir patrones
    patron_sanciones = r"SE RESUELVE:"
    patron_detalle_sanciones = (
        r"(?:sobre la determinaci[oó]n de las sanciones a aplicar|sobre la determinaci[oó]n|sobre las sanciones)"
    )
    print (texto_pag_finales)
   

    # Buscar entre los dos patrones
    m = re.search(rf"(?i){patron_detalle_sanciones}(.*?){patron_sanciones}", texto_pag_finales, re.DOTALL)
    if m:
        
                # Extraer texto a partir de SE RESUELVE:
        texto_sanciones = re.split(patron_sanciones, texto_pag_finales, maxsplit=1, flags=re.IGNORECASE)[1].strip()
        texto_detalle_sanciones = m.group(1).strip()

        parrafos_con_sanciones = extraer_parrafos_con_sanciones(texto_sanciones)
        parrafos_con_sanciones = quitar_saltos_lineas(parrafos_con_sanciones)

        

        conceptos_infracciones=obtener_conceptos_infracciones(texto_detalle_sanciones)
        conceptos_infracciones=quitar_saltos_lineas(conceptos_infracciones)
        articulos_conceptos_infracciones=obtener_articulos_conceptos_infracciones(conceptos_infracciones)
        multas = obtener_multas_2025(parrafos_con_sanciones)

        print(parrafos_con_sanciones)
        
        tipo_infraccion = obtener_tipo_infracion_2025(parrafos_con_sanciones)
        ley_tipo_infraccion = obtener_ley_tipo_infraccion_2025(parrafos_con_sanciones)

        return resolucion_directoral,conceptos_infracciones,articulos_conceptos_infracciones,tipo_infraccion,ley_tipo_infraccion,multas
    else:
        return resolucion_directoral, "",[], [], [], []
    
def eliminar_primera_linea_por_pagina(texto: str) -> str:
    """
    Elimina la primera línea con contenido que aparece inmediatamente después
    de cada separador tipo '===Fin de la página X==='.
    """
    # Patrón que detecta el separador y captura lo que sigue hasta el próximo separador o fin de texto
    separador_patron = r"(===Fin de la página \d+===\n\n)(.*?)(?=(?:===Fin de la página \d+===\n\n)|$)"

    def limpiar_bloque(match):
        separador = match.group(1)
        contenido = match.group(2)

        lineas = contenido.splitlines()
        linea_eliminada = False
        nuevas_lineas = []

        for linea in lineas:
            # Eliminar solo la primera línea con letras o números
            if not linea_eliminada and re.search(r'\w', linea):
                linea_eliminada = True
                continue
            nuevas_lineas.append(linea)

        return separador + "\n".join(nuevas_lineas)

    texto_limpio = re.sub(separador_patron, limpiar_bloque, texto, flags=re.DOTALL)
    return texto_limpio
    
def obtener_resolucion_directoral(texto):
    primera_linea = texto.splitlines()[0]
    return primera_linea

def obtener_multas_2025(lista_parrafos_con_sanciones):
    patron = re.compile(r'\d+(?:[.,]\d+)?\s*U\.?I\.?T\.?', re.IGNORECASE)
    resultados = []
    for parrafo in lista_parrafos_con_sanciones:
        resultados.extend(patron.findall(parrafo))
    return resultados

def obtener_tipo_infracion_2025(lista_parrafos_con_sanciones):
    patron = re.compile(r'infracci[oó]n\s+(\w+)', re.IGNORECASE)
    resultados = []

    for parrafo in lista_parrafos_con_sanciones:
        matches = patron.findall(parrafo)
        resultados.extend(matches)  # agregamos todos los matches del párrafo

    return resultados

def obtener_ley_tipo_infraccion_2025(lista_parrafos_con_sanciones):
    """
    Busca ocurrencias de 'literal' y extrae todo hasta el primer punto o coma.
    Devuelve una lista con los resultados por cada párrafo.
    """
    patron = re.compile(r'(literal[^.,:]+)', re.IGNORECASE)
    resultados = []

    for parrafo in lista_parrafos_con_sanciones:
        matches = patron.findall(parrafo)
        resultados.extend(matches)  # agregamos todos los matches del párrafo

    return resultados


def extraer_parrafos_con_sanciones(texto):
    """
    Extrae párrafos que contienen números decimales con coma seguidos de 'U' y 'T'
    """
    # 1. Normalizar saltos: reemplazar diferentes formas de fin de párrafo
    # Párrafo = cualquier bloque de texto terminado en un punto y salto(s) de línea
    parrafos = re.split(r'\.\s*\n(?:\s*\n)?', texto)

    # 2. Regex para detectar patrones como 2,5 U.T. o 10,75 UT
    patron= re.compile(r'\d+(?:[.,]\d+)?\s*U\.?I\.?T\.?', re.IGNORECASE)

    # 3. Filtrar párrafos que contengan el patrón
    parrafos_encontrados = [p.strip() for p in parrafos if patron.search(p)]

    return parrafos_encontrados


# ruta=r"G:\Mi unidad\Resoluciones ANPD\PDFs\2025\009_resolucion_9.pdf"
# texto=obtener_datos_pdf_2025(ruta)
# print(texto)

procesar_pdfs_en_carpeta(carpeta_pdfs,"data_resoluciones_2024.json")



    



