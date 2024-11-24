
import openai
import os
from dotenv import load_dotenv

load_dotenv()

client = openai.Client(api_key=os.environ.get("OPENAI_API_KEY"))

response = client.chat.completions.create(
    model = "gpt-4o-mini",
    messages = [
        {
            "role": "system",
            "content": "Asistente para crear silabo y plan de clases",
        }
    ]
)
messages = response.choices[0].message.content
print(messages)
