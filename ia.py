import requests
import json

def preguntar_ia_streaming(mensaje: str, historial: list = None):
    """
    historial: lista de dicts con {"role": "user"/"assistant", "content": "..."}
    """
    url = "http://localhost:11434/api/chat"
    
    # Construir mensajes para el formato chat
    messages = []
    if historial:
        messages.extend(historial)
    
    # Agregar el mensaje actual
    messages.append({
        "role": "user",
        "content": mensaje
    })
    
    data = {
        "model": "llama3.2",
        "messages": messages,
        "stream": True
    }
    
    response = requests.post(url, json=data, stream=True)
    
    for line in response.iter_lines():
        if line:
            data = json.loads(line)
            if 'message' in data and 'content' in data['message']:
                yield data['message']['content']

# Función para respuestas sin streaming (si la necesitas)
def preguntar_ia(mensaje: str, historial: list = None):
    respuesta_completa = ""
    for pedazo in preguntar_ia_streaming(mensaje, historial):
        respuesta_completa += pedazo
    return respuesta_completa