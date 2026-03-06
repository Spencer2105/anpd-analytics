# rag_multas_system.py

import json
import pandas as pd
import requests
import time
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable
import re

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class RAGMultasProcessor:
    """
    Procesador RAG simplificado para uso desde otros archivos
    """
    
    def __init__(self, modelo: str = "phi4-mini"):
        """
        Inicializa el procesador RAG
        
        Args:
            modelo: Modelo a usar ("mistral:7b" o "phi3:3.8b")
            url_ollama: URL del servidor Ollama
        """
        self.modelo = modelo
        self.timeout = 120
        self.max_reintentos = 3
        
        # Verificar conexión
        if not self._verificar_ollama():
            raise ConnectionError("❌ No se puede conectar con Ollama. ¿Está ejecutándose?")
        
        print(f"✅ Conectado a Ollama usando modelo: {modelo}")
        
        # Estadísticas
        self.stats = {
            'archivos_procesados': 0,
            'archivos_exitosos': 0,
            'archivos_fallidos': 0,
            'multas_extraidas': 0,
            'tiempo_total': 0
        }
        
        # Prompt optimizado
        self.prompt = self._get_prompt()
    
    def _verificar_ollama(self) -> bool:
        """Verifica que Ollama esté disponible"""
        try:
            response = requests.get(f"{self.url_ollama}/api/tags", timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def _get_prompt(self) -> str:
        """Prompt optimizado para extracción"""
        return '''
Eres un extractor de datos de multas. Responde ÚNICAMENTE con JSON válido.

Extrae esta información del texto:

{
  "multas": [
    {
      "multa_numero": 1,
      "concepto": "descripción breve",
      "tipo_infraccion": "LEVE|GRAVE|MUY_GRAVE", 
      "monto_base_uit": 0.0,
      "monto_final_uit": 0.0,
      "factores": {
        "cooperacion": "SI|NO|NO_MENCIONADO",
        "personas_afectadas": "0|1|MAS_DE_1|NO_ESPECIFICADO", 
        "perjuicio": "SI|NO|NO_MENCIONADO",
        "reincidencia": "0|1|MAS_DE_1|NO_MENCIONADO",
        "duracion_mayor_24_meses": "SI|NO|NO_MENCIONADO",
        "entorpecimiento_investigacion": "SI|NO|NO_MENCIONADO"
      },
      "calculo": {
        "factor_total_porcentaje": 0,
        "formula_aplicada": "descripción del cálculo"
      }
    }
  ],
  "resumen": {
    "total_multas": 0,
    "monto_total_uit": 0.0
  }
}

REGLAS:
- Solo datos explícitos del texto
- Ignora tablas mal formateadas por OCR
- Si no hay multas, devuelve estructura vacía
- Responde SOLO JSON, sin texto adicional
'''
    
    def _llamar_modelo(self, texto: str) -> Optional[str]:
        """Llama al modelo local con el texto"""
        payload = {
            "model": self.modelo,
            "prompt": f"{self.prompt}\n\nTEXTO:\n{texto}",
            "stream": False,
            "options": {
                "temperature": 0.1,
                "num_ctx": 4096
            }
        }
        
        for intento in range(self.max_reintentos):
            try:
                response = requests.post(
                    f"{self.url_ollama}/api/generate",
                    json=payload,
                    timeout=self.timeout
                )
                
                if response.status_code == 200:
                    result = response.json()
                    return result.get('response', '')
                    
            except requests.exceptions.Timeout:
                print(f"⏱️  Timeout en intento {intento + 1}")
            except Exception as e:
                print(f"❌ Error en intento {intento + 1}: {e}")
            
            if intento < self.max_reintentos - 1:
                time.sleep(5)
        
        return None
    
    def _extraer_json(self, respuesta: str) -> Optional[Dict]:
        """Extrae JSON de la respuesta del modelo"""
        try:
            # Buscar el JSON en la respuesta
            inicio = respuesta.find('{')
            fin = respuesta.rfind('}') + 1
            
            if inicio != -1 and fin > inicio:
                json_str = respuesta[inicio:fin]
                return json.loads(json_str)
                
        except json.JSONDecodeError as e:
            print(f"❌ Error parseando JSON: {e}")
            print(f"Respuesta problemática: {respuesta[:200]}...")
        
        return None
    
    def _limpiar_texto(self, texto: str) -> str:
        """Limpia el texto de elementos problemáticos"""
        # Remover tablas mal formateadas por OCR
        texto = re.sub(r'\[[\w\s"_|]+\]', '', texto)
        texto = re.sub(r'\n{3,}', '\n\n', texto)
        texto = re.sub(r' {2,}', ' ', texto)
        return texto.strip()
    
    def _tiene_contenido_relevante(self, texto: str) -> bool:
        """Verifica si hay contenido de multas"""
        palabras_clave = [
            'multa', 'sanción', 'infracción', 'UIT', 'agravante', 
            'atenuante', 'reincidencia', 'perjuicio', 'cooperación'
        ]
        texto_lower = texto.lower()
        return any(palabra in texto_lower for palabra in palabras_clave)
    
    def _dividir_texto(self, texto: str) -> List[str]:
        """Divide texto en chunks manejables"""
        # Buscar marcadores de página
        if "===Fin de la página" in texto:
            paginas = re.split(r"===Fin de la página \d+===", texto)
            return [p.strip() for p in paginas if p.strip()]
        
        # Si no hay marcadores, dividir por tamaño
        chunks = []
        for i in range(0, len(texto), 3000):
            chunks.append(texto[i:i+3000])
        return chunks
    
    def procesar_archivo_unico(self, ruta_archivo: str, texto_extraido: str) -> Optional[Dict]:
        """
        Procesa un archivo individual
        
        Args:
            ruta_archivo: Ruta del archivo PDF
            texto_extraido: Texto ya extraído del PDF
            
        Returns:
            Dict con los datos extraídos o None si falla
        """
        inicio_tiempo = time.time()
        
        try:
            print(f"🔄 Procesando: {os.path.basename(ruta_archivo)}")
            
            # Limpiar texto
            texto_limpio = self._limpiar_texto(texto_extraido)
            
            if not self._tiene_contenido_relevante(texto_limpio):
                print(f"⚠️  Sin contenido relevante")
                return None
            
            # Dividir en chunks
            chunks = self._dividir_texto(texto_limpio)
            print(f"📄 Dividido en {len(chunks)} partes")
            
            # Procesar cada chunk
            todos_resultados = []
            for i, chunk in enumerate(chunks):
                if self._tiene_contenido_relevante(chunk):
                    print(f"   Procesando parte {i+1}/{len(chunks)}")
                    
                    respuesta = self._llamar_modelo(chunk)
                    if respuesta:
                        datos = self._extraer_json(respuesta)
                        if datos and datos.get('multas'):
                            todos_resultados.append(datos)
            
            # Consolidar resultados
            if todos_resultados:
                resultado_final = self._consolidar_resultados(todos_resultados, ruta_archivo)
                
                # Agregar metadatos
                resultado_final['metadatos'] = {
                    'archivo_origen': os.path.basename(ruta_archivo),
                    'fecha_procesamiento': datetime.now().isoformat(),
                    'tiempo_procesamiento': time.time() - inicio_tiempo
                }
                
                self.stats['archivos_exitosos'] += 1
                self.stats['multas_extraidas'] += len(resultado_final.get('multas', []))
                print(f"✅ Completado - {len(resultado_final.get('multas', []))} multas extraídas")
                
                return resultado_final
            else:
                print(f"⚠️  No se encontraron multas")
                
        except Exception as e:
            print(f"❌ Error: {e}")
            self.stats['archivos_fallidos'] += 1
            
        finally:
            self.stats['archivos_procesados'] += 1
            self.stats['tiempo_total'] += time.time() - inicio_tiempo
        
        return None
    
    def _consolidar_resultados(self, resultados: List[Dict], archivo_origen: str) -> Dict:
        """Consolida múltiples resultados en uno solo"""
        consolidado = {
            "caso_info": {},
            "multas": [],
            "resumen": {"total_multas": 0, "monto_total_uit": 0.0}
        }
        
        multa_counter = 1
        
        for resultado in resultados:
            # Info del caso (usar la primera disponible)
            if not consolidado["caso_info"] and resultado.get("caso_info"):
                consolidado["caso_info"] = resultado["caso_info"]
            
            # Agregar multas
            for multa in resultado.get("multas", []):
                multa["multa_numero"] = multa_counter
                consolidado["multas"].append(multa)
                multa_counter += 1
        
        # Calcular totales
        total_multas = len(consolidado["multas"])
        monto_total = sum(m.get("monto_final_uit", 0) for m in consolidado["multas"])
        
        consolidado["resumen"] = {
            "total_multas": total_multas,
            "monto_total_uit": round(monto_total, 2)
        }
        
        return consolidado
    
    def procesar_lote_archivos(
        self, 
        archivos_pdf: List[str], 
        carpeta_base: str,
        funcion_extraccion: Callable[[str], str],
        guardar_progreso: bool = True
    ) -> tuple:
        """
        Procesa un lote de archivos PDF
        
        Args:
            archivos_pdf: Lista de nombres de archivos PDF
            carpeta_base: Carpeta donde están los PDFs
            funcion_extraccion: Función para extraer texto (tu obtener_datos_pdf_2025)
            guardar_progreso: Si guardar progreso cada 50 archivos
            
        Returns:
            tuple: (DataFrame, lista_resultados, estadísticas)
        """
        
        todos_resultados = []
        total_archivos = len(archivos_pdf)
        
        print(f"🚀 Iniciando procesamiento de {total_archivos} archivos")
        
        # Crear carpeta para backups si no existe
        if guardar_progreso:
            os.makedirs('resultados_individuales', exist_ok=True)
        
        for i, nombre_archivo in enumerate(archivos_pdf, 1):
            ruta_completa = os.path.join(carpeta_base, nombre_archivo)
            
            print(f"\n📁 [{i}/{total_archivos}] {nombre_archivo}")
            
            try:
                # Extraer texto usando la función proporcionada
                texto_extraido = funcion_extraccion(ruta_completa)
                
                if texto_extraido:
                    # Procesar con RAG
                    resultado = self.procesar_archivo_unico(ruta_completa, texto_extraido)
                    
                    if resultado:
                        todos_resultados.append(resultado)
                        
                        # Guardar backup individual
                        if guardar_progreso:
                            nombre_json = nombre_archivo.replace('.pdf', '_resultado.json')
                            with open(f'resultados_individuales/{nombre_json}', 'w', encoding='utf-8') as f:
                                json.dump(resultado, f, indent=2, ensure_ascii=False)
                else:
                    print(f"⚠️  No se pudo extraer texto")
                    
            except Exception as e:
                print(f"❌ Error fatal: {e}")
                self.stats['archivos_fallidos'] += 1
                continue
            
            # Guardar progreso cada 50 archivos
            if guardar_progreso and i % 50 == 0:
                print(f"\n💾 Guardando progreso parcial ({i} archivos)...")
                df_progreso = self.crear_dataframe(todos_resultados)
                df_progreso.to_excel(f'progreso_parcial_{i}.xlsx', index=False)
        
        # Crear DataFrame final
        df_final = self.crear_dataframe(todos_resultados)
        
        # Guardar resultados finales
        if todos_resultados:
            with open('resultados_completos.json', 'w', encoding='utf-8') as f:
                json.dump(todos_resultados, f, indent=2, ensure_ascii=False)
            
            df_final.to_excel('resultados_multas_completo.xlsx', index=False)
            print(f"\n💾 Guardado completo: {len(df_final)} registros")
        
        # Mostrar estadísticas finales
        stats_finales = self.obtener_estadisticas()
        print(f"\n📊 ESTADÍSTICAS FINALES:")
        print(f"   ✅ Exitosos: {stats_finales['archivos_exitosos']}")
        print(f"   ❌ Fallidos: {stats_finales['archivos_fallidos']}")
        print(f"   🎯 Multas: {stats_finales['multas_extraidas']}")
        print(f"   ⏱️  Tiempo: {stats_finales['tiempo_total']:.1f}s")
        if stats_finales['archivos_procesados'] > 0:
            print(f"   📈 Éxito: {(stats_finales['archivos_exitosos']/stats_finales['archivos_procesados']*100):.1f}%")
        
        return df_final, todos_resultados, stats_finales
    
    def crear_dataframe(self, resultados: List[Dict]) -> pd.DataFrame:
        """Convierte resultados a DataFrame"""
        filas = []
        
        for resultado in resultados:
            if not resultado or 'multas' not in resultado:
                continue
            
            caso_info = resultado.get('caso_info', {})
            metadatos = resultado.get('metadatos', {})
            
            for multa in resultado['multas']:
                factores = multa.get('factores', {})
                calculo = multa.get('calculo', {})
                
                fila = {
                    # Metadatos
                    'archivo_origen': metadatos.get('archivo_origen', ''),
                    'fecha_procesamiento': metadatos.get('fecha_procesamiento', ''),
                    
                    # Caso
                    'caso_id': caso_info.get('caso_id', ''),
                    'entidad': caso_info.get('entidad', ''),
                    'sancionado': caso_info.get('sancionado', ''),
                    
                    # Multa
                    'multa_numero': multa.get('multa_numero', 0),
                    'concepto': multa.get('concepto', ''),
                    'tipo_infraccion': multa.get('tipo_infraccion', ''),
                    'monto_base_uit': multa.get('monto_base_uit', 0.0),
                    'monto_final_uit': multa.get('monto_final_uit', 0.0),
                    
                    # Factores categóricos
                    'cooperacion': factores.get('cooperacion', 'NO_MENCIONADO'),
                    'personas_afectadas': factores.get('personas_afectadas', 'NO_ESPECIFICADO'),
                    'perjuicio': factores.get('perjuicio', 'NO_MENCIONADO'),
                    'reincidencia': factores.get('reincidencia', 'NO_MENCIONADO'),
                    'duracion_mayor_24_meses': factores.get('duracion_mayor_24_meses', 'NO_MENCIONADO'),
                    'entorpecimiento_investigacion': factores.get('entorpecimiento_investigacion', 'NO_MENCIONADO'),
                    
                    # Cálculo
                    'factor_total_porcentaje': calculo.get('factor_total_porcentaje', 0),
                    'formula_aplicada': calculo.get('formula_aplicada', '')
                }
                
                filas.append(fila)
        
        return pd.DataFrame(filas)
    
    def obtener_estadisticas(self) -> Dict:
        """Obtiene estadísticas del procesamiento"""
        stats = self.stats.copy()
        if stats['archivos_procesados'] > 0:
            stats['porcentaje_exito'] = (stats['archivos_exitosos'] / stats['archivos_procesados']) * 100
            stats['tiempo_promedio'] = stats['tiempo_total'] / stats['archivos_procesados']
        return stats