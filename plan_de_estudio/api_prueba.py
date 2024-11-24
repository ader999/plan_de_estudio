import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

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
    model = genai.GenerativeModel(
        model_name="gemini-1.5-pro-002",
        generation_config=generation_config
    )
    chat_session = model.start_chat()
    response = chat_session.send_message(prompt_completo)
    print(response.text)

except genai.errors.GenerativeAIError as e: # Manejo de errores más específico
    print(f"Error en la API de Gemini: {e}")
except Exception as e:
    print(f"Error general: {e}")