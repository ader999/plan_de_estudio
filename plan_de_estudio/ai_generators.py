"""
Módulo para la integración con diferentes servicios de IA.
Contiene funciones para generar respuestas de diferentes modelos de IA.
"""

import os
import json
import logging
import re
import requests
from dotenv import load_dotenv
import google.generativeai as genai


def usar_modelo_google(prompt_completo, generation_config):
    """
    Usa el modelo de Google Gemini para generar una respuesta basada en el prompt dado.

    Args:
        prompt_completo (str): Prompt que contiene las instrucciones y datos.
        generation_config (dict): Configuración para la generación del modelo.

    Returns:
        str: Respuesta generada por el modelo.
    """
    # Cargar la clave API desde .env
    load_dotenv()
    api_key = os.environ.get("GOOGLE_GENERATIVE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_GENERATIVE_API_KEY no está configurada en el archivo .env")

    try:
        # Configurar la API
        genai.configure(api_key=api_key)

        # Crear el modelo y sesión de chat
        model = genai.GenerativeModel(
            model_name="gemini-1.5-pro-latest",
            generation_config=generation_config
        )
        chat_session = model.start_chat()

        # Generar respuesta
        response = chat_session.send_message(prompt_completo)
        return response.text.strip()

    except genai.errors.GenerativeAIError as e:
        raise RuntimeError(f"Error en la API de Gemini: {e}")
    except Exception as e:
        raise RuntimeError(f"Error inesperado: {e}")


def usar_modelo_deepseek(prompt_completo, max_tokens=4000, temperature=0.7, timeout=60):
    """
    Usa el modelo de DeepSeek para generar una respuesta basada en el prompt dado.

    Args:
        prompt_completo (str): Prompt que contiene las instrucciones y datos.
        max_tokens (int): Número máximo de tokens en la respuesta.
        temperature (float): Controla la creatividad (0-1).
        timeout (int): Tiempo máximo en segundos para esperar la respuesta.

    Returns:
        str: Respuesta generada por el modelo.
    """
    # Cargar la clave API desde .env
    load_dotenv()
    api_key = os.environ.get("deepseek_API_KEY")
    if not api_key:
        logging.error("deepseek_API_KEY no está configurada en el archivo .env")
        raise ValueError("deepseek_API_KEY no está configurada en el archivo .env")

    api_url = "https://api.deepseek.com/v1/chat/completions"
    
    # Headers de la solicitud
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # Parámetros del cuerpo de la solicitud
    data = {
        "model": "deepseek-chat",  # Usar el modelo correcto según la documentación
        "messages": [
            {"role": "system", "content": "Asistente para crear sílabo y plan de clases. Genera siempre respuestas en formato JSON válido."},
            {"role": "user", "content": prompt_completo}
        ],
        "temperature": temperature,
        "max_tokens": max_tokens  # Usar el valor pasado como parámetro
    }
    
    try:
        # Hacer la solicitud POST con timeout 
        logging.info(f"Iniciando solicitud a DeepSeek con timeout={timeout} segundos")
        response = requests.post(api_url, json=data, headers=headers, timeout=timeout)
        
        # Verificar si la solicitud fue exitosa
        if response.status_code == 200:
            respuesta = response.json()
            resultado = respuesta['choices'][0]['message']['content']
            logging.info("Respuesta de DeepSeek recibida correctamente")
            logging.debug(f"Primeros 200 caracteres: {resultado[:200]}")
            return resultado
        else:
            error_message = f"Error en la API de DeepSeek: {response.status_code}, {response.text}"
            logging.error(error_message)
            raise RuntimeError(error_message)
            
    except requests.exceptions.Timeout:
        error_msg = f"Timeout al conectar con DeepSeek después de {timeout} segundos"
        logging.error(error_msg)
        # En lugar de lanzar un error, devolver una respuesta de fallback en formato JSON
        return """
        {
          "codigo": "Fallback-Error",
          "encuentros": 1,
          "fecha": "2025-04-04",
          "unidad": "Unidad I",
          "nombre_de_la_unidad": "Error de conexión",
          "contenido_tematico": "La generación automática no pudo completarse debido a problemas de red o tiempo de espera agotado.",
          "objetivo_conceptual": "Comprender los conceptos fundamentales del tema",
          "objetivo_procedimental": "Aplicar los conceptos aprendidos en ejercicios prácticos",
          "objetivo_actitudinal": "Valorar la importancia del tema estudiado",
          "tipo_primer_momento": "Evaluación diagnóstica",
          "detalle_primer_momento": "Evaluación inicial para identificar conocimientos previos",
          "tiempo_primer_momento": 20,
          "recursos_primer_momento": "Cuestionario, pizarra, marcadores",
          "tipo_segundo_momento_claseteoria": "Conferencia",
          "clase_teorica": "Exposición sobre conceptos fundamentales del tema",
          "tipo_segundo_momento_practica": "Taller",
          "clase_practica": "Resolución de ejercicios prácticos relacionados con el tema",
          "tiempo_segundo_momento": 60,
          "recursos_segundo_momento": "Computadora, proyector, ejemplos impresos",
          "tipo_tercer_momento": "Orientación del estudio independiente",
          "detalle_tercer_momento": "Asignación de tareas para resolver en casa",
          "tiempo_tercer_momento": 10,
          "recursos_tercer_momento": "Guía de ejercicios, bibliografía recomendada",
          "eje_transversal": "Tecnología de la información y comunicación",
          "detalle_eje_transversal": "Aplicación de herramientas tecnológicas para el aprendizaje",
          "actividad_aprendizaje": "Desarrollo de ejercicios prácticos sobre el tema",
          "tecnica_evaluacion": "Trabajo en grupo",
          "tipo_evaluacion": "Formativa",
          "periodo_tiempo_programado": "I Corte Evaluativo",
          "tiempo_minutos": 30,
          "agente_evaluador": "Heteroevaluación",
          "instrumento_evaluacion": "Rúbrica",
          "criterios_evaluacion": "Comprensión del tema, participación, trabajo colaborativo",
          "puntaje": 10
        }
        """
    except requests.exceptions.RequestException as e:
        error_msg = f"Error de conexión con DeepSeek: {e}"
        logging.error(error_msg)
        raise RuntimeError(error_msg)
    except Exception as e:
        error_msg = f"Error inesperado con DeepSeek: {e}"
        logging.error(error_msg)
        raise RuntimeError(error_msg)


def usar_modelo_openai(prompt_completo, model="gpt-4o-mini"):
    """
    Función para interactuar con OpenAI usando el cliente de chat.
    
    Args:
        prompt_completo (str): Prompt que contiene las instrucciones y datos.
        model (str): Modelo de OpenAI a utilizar (default: gpt-4o-mini)
        
    Returns:
        str: Respuesta generada por el modelo.
    """
    try:
        # Limpiar variables de entorno de proxy que podrían estar causando el error
        for key in ["HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy"]:
           if key in os.environ:
                del os.environ[key]
        
        # Configurar API key para OpenAI 0.28
        load_dotenv()
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY no está configurada en el archivo .env")
            
        # Configurar la API key directamente (estilo OpenAI 0.28)
        import openai
        openai.api_key = api_key
        
        # Crear el mensaje con el modelo usando la API antigua (0.28)
        completion = openai.ChatCompletion.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "Asistente para crear sílabo y plan de clases."
                },
                {
                    "role": "user",
                    "content": prompt_completo
                }
            ]
        )

        # Extraer el contenido del mensaje generado
        messages = completion.choices[0].message.content
        return messages

    except Exception as e:
        logging.error(f"Error detallado al usar OpenAI: {str(e)}")
        raise RuntimeError(f"Error al generar respuesta con OpenAI: {str(e)}")


def procesar_respuesta_ai(respuesta_ai):
    """
    Procesa la respuesta de la IA para extraer y validar el JSON.
    
    Args:
        respuesta_ai (str): Respuesta en texto del modelo de IA
        
    Returns:
        dict: Datos procesados en formato diccionario
        
    Raises:
        json.JSONDecodeError: Si hay un error al decodificar el JSON
        Exception: Para otros errores durante el procesamiento
    """
    if not respuesta_ai:
        raise ValueError('No se recibió una respuesta del modelo')
    
    logging.info("Procesando respuesta de IA...")
    logging.debug(f"Respuesta AI (primeros 200 caracteres): {respuesta_ai[:200]}...")
    
    # Buscar el JSON en la respuesta
    json_match = re.search(r'\{.*\}', respuesta_ai, re.DOTALL)
    
    if json_match:
        # Extraer el JSON encontrado
        json_str = json_match.group(0).strip()
        
        # Limpiar el string JSON (eliminar bloques de código markdown)
        json_str = re.sub(r'```json|```', '', json_str).strip()
        
        logging.debug(f"JSON extraído (primeros 200 caracteres): {json_str[:200]}...")
        
        # Intentar convertir el texto a un objeto JSON
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            logging.error(f"Error inicial al decodificar JSON: {str(e)}")
            logging.debug(f"Intentando limpiar y reparar el JSON...")
            
            # Intento adicional: reemplazar comillas simples por dobles
            json_str = json_str.replace("'", '"')
            # Intento adicional: escapar comillas internas
            json_str = re.sub(r'(?<!")(".*?)(?<!")(")', r'\1\\"', json_str)
            
            # Último intento con la corrección
            data = json.loads(json_str)
        
        # Asegurarse de que los campos esperados estén presentes
        expected_fields = ['descripcion', 'actividades', 'recursos', 'tiempo_estimado', 'criterios_evaluacion', 
                          'puntaje', 'evaluacion_sumativa', 'objetivo_conceptual', 'objetivo_procedimental', 
                          'objetivo_actitudinal', 'instrumento_cuaderno', 'instrumento_organizador', 
                          'instrumento_diario', 'instrumento_prueba']
        
        for field in expected_fields:
            if field not in data:
                data[field] = "" if field != 'tiempo_estimado' else "60"
                
            # Asegurarse de que los campos de lista sean realmente listas
            if field in ['actividades', 'recursos', 'criterios_evaluacion']:
                if not isinstance(data[field], list):
                    if data[field]:  # Si no está vacío
                        data[field] = [data[field]]
                    else:
                        data[field] = []
        
        logging.info("Datos procesados correctamente")
        return data
    else:
        # Si no hay formato JSON directo, intentar formatear la respuesta completa
        logging.warning("No se encontró un formato JSON válido en la respuesta. Creando respuesta de emergencia.")
        
        # Eliminar cualquier markdown que pueda haber
        clean_response = re.sub(r'```.*?```', '', respuesta_ai, flags=re.DOTALL).strip()
        
        # Crear un diccionario básico usando el texto completo como descripción
        data = {
            'descripcion': clean_response[:500],  # Limitar a 500 caracteres
            'actividades': ["Revisar el material proporcionado"],
            'recursos': ["Material de estudio"],
            'tiempo_estimado': "60",
            'criterios_evaluacion': ["Comprensión del contenido"],
            'puntaje': "10",
            'evaluacion_sumativa': "Evaluación basada en la comprensión del contenido",
            'objetivo_conceptual': "Comprender los conceptos fundamentales del tema",
            'objetivo_procedimental': "Aplicar los conceptos aprendidos",
            'objetivo_actitudinal': "Valorar la importancia del tema estudiado",
            'instrumento_cuaderno': "Anotaciones en el cuaderno",
            'instrumento_organizador': "Crear un organizador gráfico",
            'instrumento_diario': "Registro diario de actividades",
            'instrumento_prueba': "Evaluación escrita sobre el tema"
        }
        
        logging.info("Se generó una respuesta de emergencia al no encontrar JSON válido")
        return data


def get_default_config(modelo='google'):
    """
    Devuelve la configuración predeterminada para un modelo específico.
    
    Args:
        modelo (str): Nombre del modelo ('google', 'openai', 'deepseek')
        
    Returns:
        dict: Configuración predeterminada para el modelo
    """
    # Si no se especifica un modelo, usar google por defecto
    if not modelo:
        modelo = 'deepseek'
        
    if modelo == 'google':
        return {
            "temperature": 0.7,
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": 1524
        }
    elif modelo == 'deepseek':
        return {
            "max_tokens": 1524, 
            "temperature": 0.7, 
            "timeout": 60
        }
    elif modelo == 'openai':
        return {
            "model": "gpt-4o-mini"
        }
    else:
        # Si el modelo no es reconocido, usar configuración de google por defecto
        logging.warning(f"Modelo '{modelo}' no reconocido, usando configuración predeterminada de Google")
        return {
            "temperature": 0.7,
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": 1524
        }


def generar_respuesta_ai(prompt_completo, modelo_seleccionado='google', **kwargs):
    """
    Función unificada para generar respuestas usando el modelo de IA seleccionado.
    
    Args:
        prompt_completo (str): Prompt completo para el modelo
        modelo_seleccionado (str): Nombre del modelo a usar ('google', 'openai', 'deepseek')
        **kwargs: Parámetros adicionales específicos para cada modelo
        
    Returns:
        dict: Datos procesados de la respuesta en formato diccionario
        
    Raises:
        ValueError: Si no se puede configurar el modelo
        RuntimeError: Si hay un error durante la generación
    """
    try:
        # Si no se especifica un modelo, usar google por defecto
        if not modelo_seleccionado:
            modelo_seleccionado = 'google'
            logging.info(f"No se especificó modelo, usando {modelo_seleccionado} por defecto")
            
        respuesta_ai = None
        
        if modelo_seleccionado == 'openai':
            model = kwargs.get('model', 'gpt-4o-mini')
            respuesta_ai = usar_modelo_openai(prompt_completo, model=model)
            
        elif modelo_seleccionado == 'deepseek':
            max_tokens = kwargs.get('max_tokens', 1524)
            temperature = kwargs.get('temperature', 0.7)
            timeout = kwargs.get('timeout', 60)
            
            try:
                respuesta_ai = usar_modelo_deepseek(
                    prompt_completo, 
                    max_tokens=max_tokens, 
                    temperature=temperature, 
                    timeout=timeout
                )
                logging.info("Respuesta de DeepSeek obtenida o se generó fallback")
                
            except Exception as e:
                if "timeout" in str(e).lower() or "timed out" in str(e).lower():
                    # Crear contexto básico para respuesta de fallback
                    info_contexto = kwargs.get('info_contexto', {})
                    info_asignatura = info_contexto.get('asignatura', 'la asignatura')
                    info_carrera = info_contexto.get('carrera', 'la carrera')
                    info_unidad = info_contexto.get('unidad', 'Unidad actual')
                    info_contenido = info_contexto.get('contenido', 'el tema de estudio')
                    numero_guia = info_contexto.get('numero_guia', '1')
                    
                    # Crear respuesta de fallback
                    respuesta_ai = generar_fallback_json(
                        info_asignatura, 
                        info_carrera, 
                        info_unidad, 
                        info_contenido,
                        numero_guia
                    )
                else:
                    raise e
                    
        else:  # google por defecto
            generation_config = kwargs.get('generation_config', get_default_config('google'))
            respuesta_ai = usar_modelo_google(prompt_completo, generation_config)
        
        # Procesar la respuesta
        return procesar_respuesta_ai(respuesta_ai)
        
    except Exception as e:
        error_msg = f'Error al generar respuesta con {modelo_seleccionado}: {str(e)}'
        logging.error(error_msg)
        raise RuntimeError(error_msg)


def generar_fallback_json(info_asignatura, info_carrera, info_unidad, info_contenido, numero_guia="1"):
    """
    Genera una respuesta de fallback en formato JSON cuando hay errores de conexión.
    
    Args:
        info_asignatura (str): Nombre de la asignatura
        info_carrera (str): Nombre de la carrera
        info_unidad (str): Unidad o tema actual
        info_contenido (str): Contenido específico
        numero_guia (str): Número de la guía
        
    Returns:
        str: JSON con información de fallback
    """
    return f"""
    {{
      "descripcion": "Esta guía de estudio independiente #{numero_guia} para {info_asignatura} de {info_carrera} está enfocada en {info_unidad}. El estudiante deberá profundizar en {info_contenido} mediante investigación autodirigida, análisis crítico y aplicación práctica de los conocimientos. Esta guía promueve el desarrollo de habilidades de autorregulación y pensamiento crítico, fundamentales para el éxito académico y profesional.",
      
      "actividades": [
        "Realizar una lectura comprensiva de los materiales asignados sobre {info_contenido}",
        "Elaborar un mapa conceptual que sintetice los conceptos principales del tema",
        "Resolver los ejercicios propuestos aplicando los conocimientos adquiridos",
        "Investigar ejemplos prácticos de aplicación del contenido en contextos reales",
        "Participar en el foro de discusión compartiendo reflexiones sobre el tema estudiado"
      ],
      
      "recursos": [
        "Material bibliográfico proporcionado por el docente",
        "Presentaciones y apuntes de clase disponibles en el aula virtual",
        "Recursos digitales complementarios (artículos, videos, simulaciones)",
        "Bases de datos académicas para consulta e investigación",
        "Software especializado según requerimientos de la asignatura"
      ],
      
      "tiempo_estimado": "120",
      
      "criterios_evaluacion": [
        "Comprensión de los conceptos fundamentales del tema (40%)",
        "Capacidad de análisis y síntesis de la información (20%)",
        "Aplicación práctica de los conocimientos adquiridos (25%)",
        "Claridad y coherencia en la presentación de resultados (15%)"
      ],
      
      "puntaje": "15",
      
      "evaluacion_sumativa": "La evaluación sumativa de esta guía se realizará mediante la entrega de un informe escrito que incluya: 1) Síntesis conceptual del tema estudiado, 2) Resolución de problemas o casos prácticos, 3) Reflexión crítica sobre la aplicabilidad de los conocimientos adquiridos. Se valorará la profundidad del análisis, la correcta aplicación de conceptos y la capacidad de establecer conexiones entre teoría y práctica.",
      
      "objetivo_conceptual": "Comprender en profundidad los fundamentos teóricos de {info_contenido}, identificando sus principios, componentes y relaciones con otros temas de la asignatura, para construir una base conceptual sólida que permita avanzar hacia aplicaciones más complejas.",
      
      "objetivo_procedimental": "Desarrollar habilidades para aplicar los conocimientos adquiridos sobre {info_contenido} en la resolución de problemas prácticos, utilizando métodos, técnicas y procedimientos apropiados que demuestren dominio de los aspectos operativos del tema.",
      
      "objetivo_actitudinal": "Valorar la importancia de {info_contenido} en el contexto profesional de {info_carrera}, desarrollando una actitud crítica, responsable y ética frente al conocimiento y sus aplicaciones en situaciones reales.",
      
      "instrumento_cuaderno": "El estudiante utilizará su cuaderno para registrar conceptos clave, definiciones, fórmulas y procedimientos importantes relacionados con {info_contenido}. Se evaluará la organización, claridad y precisión de las anotaciones, así como la capacidad de estructurar la información de manera lógica y coherente.",
      
      "instrumento_organizador": "El estudiante elaborará un organizador gráfico (mapa conceptual, diagrama de flujo o cuadro sinóptico) que represente de manera visual las relaciones entre los conceptos principales de {info_contenido}. Se evaluará la jerarquización de ideas, el establecimiento de conexiones significativas y la síntesis de información compleja.",
      
      "instrumento_diario": "El estudiante llevará un diario de aprendizaje donde registrará diariamente: 1) Conceptos aprendidos sobre {info_contenido}, 2) Dificultades encontradas, 3) Estrategias utilizadas para superar obstáculos, 4) Reflexiones sobre aplicaciones prácticas del tema. Se evaluará la consistencia, profundidad de reflexión y evolución del aprendizaje.",
      
      "instrumento_prueba": "Se realizará una prueba escrita que incluirá: preguntas de comprensión conceptual, problemas de aplicación y casos para análisis relacionados con {info_contenido}. La prueba evaluará tanto el dominio teórico como la capacidad de transferir conocimientos a situaciones nuevas."
    }}
    """
