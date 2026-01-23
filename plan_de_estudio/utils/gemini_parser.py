
import os
import io
import json
import docx
import google.generativeai as genai

# Configure Gemini
def configure_gemini():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not found in environment variables.")
    genai.configure(api_key=api_key)

from docx.document import Document
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import _Cell, Table
from docx.text.paragraph import Paragraph

def extract_text_from_docx(docx_file):
    """Extracts text from a docx file, preserving the order of paragraphs and tables."""
    doc = docx.Document(docx_file)
    full_text = []

    # Helper to iterate over body elements in order
    def iter_block_items(parent):
        if isinstance(parent, Document):
            parent_elm = parent.element.body
        elif isinstance(parent, _Cell):
            parent_elm = parent._tc
        else:
            raise ValueError("something's not right")

        for child in parent_elm.iterchildren():
            if isinstance(child, CT_P):
                yield Paragraph(child, parent)
            elif isinstance(child, CT_Tbl):
                yield Table(child, parent)

    for block in iter_block_items(doc):
        if isinstance(block, Paragraph):
            if block.text.strip():
                full_text.append(block.text)
        elif isinstance(block, Table):
            # Represent table as pseudo-markdown or clearly delimited structure
            table_text = []
            table_text.append("\n--- TABLE START ---")
            for row in block.rows:
                row_cells = [cell.text.strip().replace("\n", " ") for cell in row.cells]
                table_text.append(" | ".join(row_cells))
            table_text.append("--- TABLE END ---\n")
            full_text.append("\n".join(table_text))
            
    return "\n\n".join(full_text)

def parse_curriculum_with_ai(docx_file):
    """
    Parses a curriculum .docx file using Gemini and returns a JSON dictionary 
    compatible with ProgramaAsignatura2026 model.
    """
    configure_gemini()
    
    # Extract text preserving order
    text_content = extract_text_from_docx(docx_file)
    
    # Define the schema/prompt
    prompt = """
    You are an expert curriculum analyzer. I will provide you with the text content of a university course syllabus/program.
    Your task is to extract specific information and map it to the following JSON structure.
    
    Target JSON Structure (keys match Django model fields):
    {
        "fundamentacion": "String",
        "relacion_unidades": "String",
        "aportes_perfil": "String",
        "valores": "String",
        "ejes_transversales": "String",
        "objetivo_conceptual": "String (General Conceptual Objective)",
        "objetivo_procedimental": "String (General Procedimental Objective)",
        "objetivo_actitudinal": "String (General Actitudinal Objective)",
        "bibliografia_basica": "String",
        "bibliografia_complementaria": "String",
        "webgrafia": "String",
        
        "unidad_1_nombre": "String",
        "unidad_1_horas_teoricas": Integer,
        "unidad_1_horas_practicas": Integer,
        "unidad_1_horas_independientes": Integer,
        "unidad_1_objetivos_especificos": "String (All specific objectives combined)",
        "unidad_1_contenido": "String (All content topics combined)",
        "unidad_1_mediacion": "String (Mediación Pedagógica)",
        "unidad_1_evaluacion": "String",

        "unidad_2_nombre": "String",
        "unidad_2_horas_teoricas": Integer,
        "unidad_2_horas_practicas": Integer,
        "unidad_2_horas_independientes": Integer,
        "unidad_2_objetivos_especificos": "String",
        "unidad_2_contenido": "String",
        "unidad_2_mediacion": "String",
        "unidad_2_evaluacion": "String",

        ... (Repeat for units 3, 4, 5, 6 as needed)
    }
    
    CRITICAL INSTRUCTIONS:
    1. **Hours (HT, HP, HTI)**: 
       - Look for the table entitled "PLAN TEMÁTICO" or similar (it is marked with --- TABLE START ---).
       - It often has columns like "UNIDADES TEMÁTICAS", "HT", "HP", "HTI".
       - Map the rows to the corresponding units. Note that the unit NAME in the JSON should match the unit name in the table.
       - IMPORTANT: "HT" = horas_teoricas, "HP" = horas_practicas, "HTI" = horas_independientes.
       - If a unit has NO hours listed, use 0.

    2. **Bibliography**: 
       - Look for the section "BIBLIOGRAFÍA BÁSICA Y COMPLEMENTARIA" near the end of the document.
       - Be careful to capture the FULL list of references.

    3. **Units details**: 
       - Combine all specific objectives for a unit into one string.
       - Combine all thematic content for a unit into one string.
       - Look for specific Mediation and Evaluation strategies per unit if available.

    4. **Input Data**: The input text preserves the document structure. Tables are marked.

    5. Return ONLY valid JSON.
    """
    
    # We remove the truncation. Gemini 1.5/pro/flash has a very large context window.
    # We trust it can handle the full syllabus.
    full_prompt = prompt + "\n\n" + text_content 
    
    model = genai.GenerativeModel('gemini-3-flash-preview')
    response = model.generate_content(full_prompt)
    
    try:
        # Clean response if it contains markdown code blocks
        clean_response = response.text.replace("```json", "").replace("```", "").strip()
        data = json.loads(clean_response)
        return data
    except Exception as e:
        print(f"Error parsing AI response: {e}")
        print(f"Response text: {response.text}")
        return {}

