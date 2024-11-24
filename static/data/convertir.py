import csv
import json

def csv_a_json(ruta_csv, ruta_json):
    # Abrir archivo CSV y leer los datos
    with open(ruta_csv, mode='r', encoding='utf-8') as archivo_csv:
        lector_csv = csv.DictReader(archivo_csv)
        
        # Convertir cada fila del CSV en un diccionario y añadirlo a una lista
        datos = [fila for fila in lector_csv]
        
    # Escribir datos en formato JSON
    with open(ruta_json, mode='w', encoding='utf-8') as archivo_json:
        json.dump(datos, archivo_json, indent=4, ensure_ascii=False)
        
    print(f"Datos convertidos y guardados en {ruta_json}")

# Ruta del archivo CSV y la salida en JSON
ruta_csv = 'datosparaelmodelo.csv'
ruta_json = 'datos.json'

csv_a_json(ruta_csv, ruta_json)

