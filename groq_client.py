import requests
import json
import os
from dotenv import load_dotenv
import os

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")


def preguntar_groq_streaming(mensaje: str, historial: list = None, modelo: str = "llama-3.1-8b-instant"):
    """
    historial: lista de dicts con {"role": "user"/"assistant", "content": "..."}
    """
    url = "https://api.groq.com/openai/v1/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    messages = []
    if historial:
        messages.extend(historial)
    
    messages.append({
        "role": "user",
        "content": mensaje
    })
    
    data = {
        "model": modelo,
        "messages": messages,
        "stream": True,
        "temperature": 0.7,
        "max_tokens": 2048
    }
    
    response = requests.post(url, headers=headers, json=data, stream=True)
    
    for line in response.iter_lines():
        if line:
            line = line.decode('utf-8')
            if line.startswith('data: '):
                line = line[6:]  # Quitar "data: "
                if line == '[DONE]':
                    break
                try:
                    data = json.loads(line)
                    if 'choices' in data and len(data['choices']) > 0:
                        delta = data['choices'][0].get('delta', {})
                        if 'content' in delta:
                            yield delta['content']
                except json.JSONDecodeError:
                    pass

def preguntar_groq(mensaje: str, historial: list = None, modelo: str = "llama-3.1-8b-instant"):
    respuesta_completa = ""
    for pedazo in preguntar_groq_streaming(mensaje, historial, modelo):
        respuesta_completa += pedazo
    return respuesta_completa

# Prueba
if __name__ == "__main__":
    print("=== Groq Streaming ===")
    for pedazo in preguntar_groq_streaming("Hola, ¿cómo estás?"):
        print(pedazo, end="", flush=True)
    print("\n")
    
    print("=== Groq Completo ===")
    respuesta = preguntar_groq("Dame 3 consejos de productividad")
    print(respuesta)