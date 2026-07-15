import os
from google import genai
from google.genai.errors import APIError
from dotenv import load_dotenv

load_dotenv()
client = genai.Client()

filepath = "../static/data/datos_ejemplo.txt"  # Corrección del nombre del archivo

try:
    with open(filepath, 'r') as file:
        datos_ejemplo = file.read()
except FileNotFoundError:
    print(f"Error: El archivo '{filepath}' no se encuentra.")
    exit()

prompt_usuario = input("Describe las características del sílabo que deseas generar: ")

prompt_completo = f"""
Instrucciones: Crea un sílabo basado en la siguiente información.

Datos de ejemplo (para tu referencia):

{datos_ejemplo}


Solicitud del usuario:
{prompt_usuario}

"""

generation_config = {
    "temperature": 0.7,
    "max_output_tokens": 2024
}

try:
    response = client.models.generate_content(
        model="gemini-1.5-pro-002",
        contents=prompt_completo,
        config=generation_config
    )
    print(response.text)

except APIError as e: # Manejo de errores más específico
    print(f"Error en la API de Gemini: {e}")
except Exception as e:
    print(f"Error general: {e}")