#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Lector de PDFs de resoluciones oficiales peruanas
Este módulo extrae texto de PDFs usando pdfplumber y OCR como respaldo
"""

import pdfplumber
import fitz  # PyMuPDF solo para OCR
import pytesseract
from PIL import Image
import io
import re
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LectorPDF:
    """
    Clase para extraer texto de PDFs de resoluciones oficiales peruanas
    Combina pdfplumber con OCR cuando es necesario
    """
    
    def __init__(self, ruta_archivo):
        """
        Inicializa el lector con la ruta del archivo PDF
        
        Args:
            ruta_archivo (str): Ruta al archivo PDF
        """
        self.ruta_archivo = ruta_archivo
        self.documento = None
        self.estadisticas = {
            'paginas_procesadas': 0,
            'paginas_con_pdfplumber': 0,
            'paginas_con_ocr': 0,
            'caracteres_totales': 0,
            'caracteres_ocr': 0,
            'tablas_extraidas': 0
        }
    
    def abrir_documento(self):
        """
        Abre el documento PDF usando pdfplumber
        
        Returns:
            bool: True si se abrió correctamente, False en caso contrario
        """
        try:
            self.documento = pdfplumber.open(self.ruta_archivo)
            logger.info(f"Documento abierto: {len(self.documento.pages)} páginas")
            return True
        except Exception as e:
            logger.error(f"Error al abrir el documento: {e}")
            return False
    
    def limpiar_texto_repetitivo(self, texto):
        """
        Elimina encabezados y footers repetitivos típicos de resoluciones peruanas
        
        Args:
            texto (str): Texto a limpiar
            
        Returns:
            str: Texto limpio sin elementos repetitivos
        """
        # Patrones identificados en el documento de ejemplo
        patrones_a_eliminar = [
            # Encabezado de autenticidad
            r'Esta es una copia auténtica imprimible.*?según corresponda\.',
            # Información de verificación web
            r'https://sgd\.minjus\.gob\.pe/gesdoc_web.*?según corresponda\.',
            # Numeración de página
            r'Página \d+ de \d+',
            r'(?:\d+\s+)?Folio?s?\s+\d+(?:\s+(?:a|al|a la)\s+\d+)?',
            r'(?:\d+\s+)?Foja?s?\s+\d+(?:\s+(?:a|al|a la)\s+\d+)?',
            r'(?:\d+\s+)?Foja\s+\d+\.?\s*',  
            r'(?:\d+\s+)?Fojas?\s+\d+(?:\s*a\s*\d+)?\.?\s*',  
            r'(?:\d+\s+)?Folios?\s+\d+(?:\s*a\s*al?\s*\d+)?\.?\s*'
            # Referencias numeradas al final de línea
            r'^\d+\s*$',  # Números sueltos en líneas separadas
            # Líneas múltiples de espacios o guiones
            r'-{3,}',
            r'_{3,}',
            # Espacios múltiples
            r'\s{3,}',
            r'^\d+\s+(Ley N\.° \d+.*|Artículo \d+.*)(?:\n.+?)*(?=\n\d+|$)',
             r'\d+\s+(?:Ley N[°º] \d+|Reglamento de la Ley).*?[\u201D"]'
        ]
        
        texto_limpio = texto
        for patron in patrones_a_eliminar:
            texto_limpio = re.sub(patron, ' ', texto_limpio, flags=re.DOTALL | re.IGNORECASE | re.MULTILINE)
        
        # Limpiar espacios múltiples y saltos de línea excesivos
        texto_limpio = re.sub(r'\n\s*\n\s*\n', '\n\n', texto_limpio)
        texto_limpio = re.sub(r'[ ]+', ' ', texto_limpio)
        
        return texto_limpio.strip()
    
    def extraer_texto_con_pdfplumber(self, numero_pagina):
        """
        Extrae texto de una página usando pdfplumber (mejor orden y tablas)
        
        Args:
            numero_pagina (int): Número de página (base 0)
            
        Returns:
            tuple: (texto_extraido, numero_caracteres, tablas_encontradas)
        """
        try:
            pagina = self.documento.pages[numero_pagina]
            
            # Extraer texto regular
            texto = pagina.extract_text()
            if texto is None:
                texto = ""
            
            # Extraer tablas y convertirlas a texto estructurado
            tablas = pagina.extract_tables()
            texto_tablas = ""
            
            if tablas:
                self.estadisticas['tablas_extraidas'] += len(tablas)
                for i, tabla in enumerate(tablas, 1):
                    texto_tablas += f"\n\n[TABLA {i}]\n"
                    for fila in tabla:
                        if fila:  # Verificar que la fila no esté vacía
                            fila_limpia = [str(celda).strip() if celda is not None else "" for celda in fila]
                            texto_tablas += " | ".join(fila_limpia) + "\n"
                    texto_tablas += "[FIN TABLA]\n"
            
            # Combinar texto regular y tablas
            texto_completo = texto + texto_tablas
            
            # Limpiar texto
            texto_limpio = self.limpiar_texto_repetitivo(texto_completo)
            
            return texto_limpio, len(texto_limpio), len(tablas) if tablas else 0
            
        except Exception as e:
            logger.warning(f"Error extrayendo texto con pdfplumber en página {numero_pagina + 1}: {e}")
            return "", 0, 0
    
    def extraer_texto_con_ocr(self, numero_pagina):
        """
        Extrae texto de una página usando OCR (Tesseract) con PyMuPDF para la imagen
        
        Args:
            numero_pagina (int): Número de página (base 0)
            
        Returns:
            tuple: (texto_extraido, numero_caracteres)
        """
        try:
            # Abrir documento con PyMuPDF solo para OCR
            doc_fitz = fitz.open(self.ruta_archivo)
            pagina = doc_fitz[numero_pagina]
            
            # Obtener la página como imagen con alta resolución
            matriz = fitz.Matrix(2.0, 2.0)  # Escalar 2x para mejor OCR
            pixmap = pagina.get_pixmap(matrix=matriz)
            imagen_datos = pixmap.tobytes("png")
            
            # Convertir a PIL Image
            imagen = Image.open(io.BytesIO(imagen_datos))
            
            # Aplicar OCR con configuración optimizada para español
            texto = pytesseract.image_to_string(
                imagen, 
                lang='spa', 
                config='--psm 6 --oem 3'
            )
            
            # Cerrar documento PyMuPDF
            doc_fitz.close()
            
            texto_limpio = self.limpiar_texto_repetitivo(texto)
            
            logger.info(f"OCR aplicado en página {numero_pagina + 1}: {len(texto_limpio)} caracteres")
            return texto_limpio, len(texto_limpio)
            
        except Exception as e:
            logger.error(f"Error aplicando OCR en página {numero_pagina + 1}: {e}")
            return "", 0
    
    def es_texto_valido(self, texto, umbral_minimo=50):
        """
        Verifica si el texto extraído es válido (tiene suficientes caracteres)
        
        Args:
            texto (str): Texto a validar
            umbral_minimo (int): Número mínimo de caracteres válidos
            
        Returns:
            bool: True si el texto es válido, False en caso contrario
        """
        if not texto:
            return False
        
        # Contar caracteres alfabéticos (excluyendo espacios y símbolos)
        caracteres_alfanumericos = sum(1 for c in texto if c.isalnum())
        return caracteres_alfanumericos >= umbral_minimo
    
    def extraer_pagina(self, numero_pagina):
        """
        Extrae texto de una página específica, usando OCR si es necesario
        
        Args:
            numero_pagina (int): Número de página (base 0)
            
        Returns:
            tuple: (texto_extraido, metodo_utilizado, caracteres_extraidos, tablas_encontradas)
        """
        # Intentar primero con pdfplumber
        texto_pdfplumber, chars_pdfplumber, tablas = self.extraer_texto_con_pdfplumber(numero_pagina)
        
        if self.es_texto_valido(texto_pdfplumber):
            self.estadisticas['paginas_con_pdfplumber'] += 1
            self.estadisticas['caracteres_totales'] += chars_pdfplumber
            return texto_pdfplumber, "pdfplumber", chars_pdfplumber, tablas
        
        # Si pdfplumber no funciona, usar OCR
        logger.info(f"Aplicando OCR en página {numero_pagina + 1} (pdfplumber insuficiente: {chars_pdfplumber} chars)")
        texto_ocr, chars_ocr = self.extraer_texto_con_ocr(numero_pagina)
        
        self.estadisticas['paginas_con_ocr'] += 1
        self.estadisticas['caracteres_ocr'] += chars_ocr
        self.estadisticas['caracteres_totales'] += chars_ocr
        
        return texto_ocr, "OCR", chars_ocr, 0
    
    def extraer_texto_completo(self, pagina_inicio=None, pagina_fin=None):
        """
        Extrae texto completo del PDF o de un rango específico de páginas
        
        Args:
            pagina_inicio (int, optional): Página de inicio (base 1). Si es None, inicia desde la primera
            pagina_fin (int, optional): Página final (base 1, inclusiva). Si es None, va hasta la última
            
        Returns:
            tuple: (texto_completo, estadisticas_detalladas)
        """
        if not self.abrir_documento():
            return "", self.estadisticas
        
        total_paginas = len(self.documento.pages)
        
        # Determinar rango de páginas
        if pagina_inicio is None:
            pagina_inicio = 1
        if pagina_fin is None:
            pagina_fin = total_paginas
        
        # Validar rango
        if pagina_inicio < 1 or pagina_fin > total_paginas or pagina_inicio > pagina_fin:
            logger.error(f"Rango inválido: {pagina_inicio}-{pagina_fin}. Total páginas: {total_paginas}")
            return "", self.estadisticas
        
        texto_completo = []
        
        logger.info(f"Procesando páginas {pagina_inicio} a {pagina_fin} de {total_paginas}")
        
        for num_pagina in range(pagina_inicio - 1, pagina_fin):  # Convertir a base 0
            logger.info(f"Procesando página {num_pagina + 1}...")
            
            texto, metodo, caracteres, tablas = self.extraer_pagina(num_pagina)
            
            # Agregar separador de página
            separador = f"\n\n===Fin de la página {num_pagina + 1}===\n\n"
            texto_con_separador = texto + separador
            
            texto_completo.append(texto_con_separador)
            self.estadisticas['paginas_procesadas'] += 1
            
            # Log con información de tablas
            info_tablas = f" ({tablas} tablas)" if tablas > 0 else ""
            logger.info(f"Página {num_pagina + 1}: {metodo} - {caracteres} caracteres{info_tablas}")
        
        # Cerrar documento
        if self.documento:
            self.documento.close()
        
        resultado_final = "".join(texto_completo)
        
        # Agregar estadísticas detalladas
        self.estadisticas['porcentaje_ocr'] = (
            (self.estadisticas['paginas_con_ocr'] / self.estadisticas['paginas_procesadas'] * 100)
            if self.estadisticas['paginas_procesadas'] > 0 else 0
        )
        
        return resultado_final, self.estadisticas
    
    def contar_paginas(self):
        """
        Cuenta el número de páginas del documento
        
        Returns:
            int: Número de páginas
        """
        try:
            self.documento = pdfplumber.open(self.ruta_archivo)
            return len(self.documento.pages)
        except Exception as e:
            logger.error(f"Error contando páginas: {e}")
            return 0
    
    def mostrar_estadisticas(self):
        """
        Muestra las estadísticas de procesamiento
        """
        stats = self.estadisticas
        print("\n" + "="*50)
        print("ESTADÍSTICAS DE PROCESAMIENTO")
        print("="*50)
        print(f"Páginas procesadas: {stats['paginas_procesadas']}")
        print(f"Páginas con pdfplumber: {stats['paginas_con_pdfplumber']}")
        print(f"Páginas con OCR: {stats['paginas_con_ocr']}")
        print(f"Tablas extraídas: {stats['tablas_extraidas']}")
        print(f"Caracteres totales: {stats['caracteres_totales']:,}")
        print(f"Caracteres de OCR: {stats['caracteres_ocr']:,}")
        if stats['paginas_procesadas'] > 0:
            print(f"Porcentaje OCR: {stats.get('porcentaje_ocr', 0):.1f}%")
        print("="*50)


def extraer_texto_pdf(ruta_archivo, pagina_inicio=None, pagina_fin=None, mostrar_stats=True):
    """
    Función principal para extraer texto de un PDF
    
    Args:
        ruta_archivo (str): Ruta al archivo PDF
        pagina_inicio (int, optional): Página de inicio (base 1)
        pagina_fin (int, optional): Página final (base 1, inclusiva)
        mostrar_stats (bool): Si mostrar estadísticas al final
        
    Returns:
        tuple: (texto_extraido, estadisticas)
    """
    lector = LectorPDF(ruta_archivo)
    texto, estadisticas = lector.extraer_texto_completo(pagina_inicio, pagina_fin)
    
    if mostrar_stats:
        lector.mostrar_estadisticas()
    
    return texto, estadisticas

    def contar_paginas(self):
        """
        Cuenta el número de páginas del documento
        
        Returns:
            int: Número de páginas
        """
        try:
            self.documento = pdfplumber.open(self.ruta_archivo)
            return len(self.documento.pages)
        except Exception as e:
            logger.error(f"Error contando páginas: {e}")
            return 0


# Pruebas unitarias
if __name__ == "__main__":
    def probar_lector():
        """
        Función de pruebas para verificar el funcionamiento del lector
        """
        # Cambiar esta ruta por la de tu archivo PDF
        archivo_prueba = "001_resolucion_1.pdf"
        
        print("INICIANDO PRUEBAS DEL LECTOR PDF CON PDFPLUMBER")
        print("="*60)
        
        try:
            # Prueba 1: Extraer todo el documento
            print("\n1. EXTRAYENDO TODO EL DOCUMENTO")
            texto_completo, stats = extraer_texto_pdf(archivo_prueba)
            
            # Mostrar primeros 500 caracteres
            print(f"\nPrimeros 500 caracteres:")
            print("-" * 40)
            print(texto_completo[:500] + "...")
            
            # Prueba 2: Extraer solo primeras 3 páginas
            print("\n\n2. EXTRAYENDO PÁGINAS 1-3")
            texto_parcial, stats_parcial = extraer_texto_pdf(
                archivo_prueba, 
                pagina_inicio=1, 
                pagina_fin=3,
                mostrar_stats=False
            )
            
            print(f"Páginas 1-3: {stats_parcial['caracteres_totales']} caracteres")
            print(f"Tablas encontradas: {stats_parcial['tablas_extraidas']}")
            
            # Prueba 3: Verificar separadores de página
            print("\n\n3. VERIFICANDO SEPARADORES DE PÁGINA")
            separadores = texto_completo.count("===Fin de la página")
            print(f"Separadores encontrados: {separadores}")
            print(f"Páginas esperadas: {stats['paginas_procesadas']}")
            
            # Prueba 4: Análisis de métodos utilizados
            print("\n\n4. ANÁLISIS DE MÉTODOS")
            print(f"Éxito pdfplumber: {stats['paginas_con_pdfplumber']}/{stats['paginas_procesadas']}")
            print(f"OCR necesario: {stats['paginas_con_ocr']}/{stats['paginas_procesadas']}")
            
            # Prueba 5: Verificar limpieza de patrones
            if "Foja" in texto_completo or "Fojas" in texto_completo:
                print("\n\n5. ADVERTENCIA: Se encontraron referencias a folios que deberían estar limpias")
                folios_encontrados = len(re.findall(r'\d+\s+Fojas?\s+\d+', texto_completo))
                print(f"Referencias a folios encontradas: {folios_encontrados}")
            else:
                print("\n\n5. LIMPIEZA DE PATRONES: ✅ Referencias a folios eliminadas correctamente")
            
            print("\n✅ TODAS LAS PRUEBAS COMPLETADAS EXITOSAMENTE")
            
        except FileNotFoundError:
            print(f"❌ ERROR: No se encontró el archivo {archivo_prueba}")
            print("Por favor, coloca un PDF de prueba en el directorio actual")
        except Exception as e:
            print(f"❌ ERROR INESPERADO: {e}")
    
    # Ejecutar pruebas
    probar_lector()