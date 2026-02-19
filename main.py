from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import json
import os
import hashlib
import secrets
from dotenv import load_dotenv
import os

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Para Groq
try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False

import requests

app = FastAPI()

# CORS para que cualquier app pueda conectarse
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

USERS_FILE = "users.json"
HISTORIAL_FILE = "historial.json"

# GROQ desde variable de entorno (más seguro)
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "GROQ_API_KEY")
GROQ_MODEL_DEFAULT = "llama-3.1-8b-instant"

def hash_password(password: str, salt: str = None):
    if salt is None:
        salt = secrets.token_hex(16)
    hashed = hashlib.sha256((password + salt).encode()).hexdigest()
    return hashed, salt

def cargar_json(archivo, default=None):
    if default is None:
        default = {}
    if not os.path.exists(archivo):
        return default
    try:
        with open(archivo, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return default

def guardar_json(archivo, datos):
    with open(archivo, "w", encoding="utf-8") as f:
        json.dump(datos, f, indent=2, ensure_ascii=False)

def preguntar_ollama_streaming(mensaje: str, historial: list = None, modelo: str = "llama3.2"):
    url = "http://localhost:11434/api/chat"
    messages = []
    if historial:
        messages.extend(historial)
    messages.append({"role": "user", "content": mensaje})
    
    data = {
        "model": modelo,
        "messages": messages,
        "stream": True
    }
    
    try:
        response = requests.post(url, json=data, stream=True, timeout=300)
        for line in response.iter_lines():
            if line:
                data = json.loads(line)
                if 'message' in data and 'content' in data['message']:
                    yield data['message']['content']
    except Exception as e:
        yield f"[Error Ollama: {str(e)}]"

def preguntar_groq_streaming(mensaje: str, historial: list = None, modelo: str = None):
    if not GROQ_AVAILABLE:
        yield "[Error: pip install groq]"
        return
    
    if not GROQ_API_KEY or not GROQ_API_KEY.startswith("gsk-"):
        yield "[Error: GROQ_API_KEY no configurada]"
        return
    
    if modelo is None:
        modelo = GROQ_MODEL_DEFAULT
    
    try:
        client = Groq(api_key=GROQ_API_KEY)
        messages = []
        if historial:
            messages.extend(historial)
        messages.append({"role": "user", "content": mensaje})
        
        stream = client.chat.completions.create(
            model=modelo,
            messages=messages,
            stream=True,
            temperature=0.7,
            max_tokens=2048
        )
        
        for chunk in stream:
            if chunk.choices[0].delta.content is not None:
                yield chunk.choices[0].delta.content
                
    except Exception as e:
        yield f"[Error Groq: {str(e)}]"

@app.post("/registro")
def registro(username: str, password: str):
    usuarios = cargar_json(USERS_FILE)
    if username in usuarios:
        raise HTTPException(status_code=400, detail="Usuario ya existe")
    
    hashed, salt = hash_password(password)
    usuarios[username] = {
        "password": hashed,
        "salt": salt,
        "creado": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "modo_ia": "local"
    }
    guardar_json(USERS_FILE, usuarios)
    return {"mensaje": "Usuario creado", "username": username}

@app.post("/login")
def login(username: str, password: str):
    usuarios = cargar_json(USERS_FILE)
    if username not in usuarios:
        raise HTTPException(status_code=401, detail="Usuario no existe")
    
    user = usuarios[username]
    hashed_input, _ = hash_password(password, user["salt"])
    
    if hashed_input != user["password"]:
        raise HTTPException(status_code=401, detail="Contraseña incorrecta")
    
    return {
        "mensaje": "Login exitoso",
        "username": username,
        "modo_ia": user.get("modo_ia", "local")
    }

@app.get("/modo_ia/{username}")
def obtener_modo_ia(username: str):
    usuarios = cargar_json(USERS_FILE)
    if username not in usuarios:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return {"modo_ia": usuarios[username].get("modo_ia", "local")}

@app.post("/modo_ia/{username}")
def cambiar_modo_ia(username: str, modo: str):
    if modo not in ["local", "online"]:
        raise HTTPException(status_code=400, detail="Modo debe ser 'local' o 'online'")
    
    usuarios = cargar_json(USERS_FILE)
    if username not in usuarios:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    usuarios[username]["modo_ia"] = modo
    guardar_json(USERS_FILE, usuarios)
    return {"mensaje": f"Modo cambiado a {modo}", "modo_ia": modo}

@app.get("/ia/{username}/{pregunta}")
def consultar_ia(username: str, pregunta: str, modo: str = None):
    usuarios = cargar_json(USERS_FILE)
    historial_db = cargar_json(HISTORIAL_FILE)
    
    if modo is None:
        modo = usuarios.get(username, {}).get("modo_ia", "local")
    
    historial_usuario = historial_db.get(username, [])
    contexto = []
    for item in historial_usuario[-5:]:
        contexto.append({"role": "user", "content": item["pregunta"]})
        contexto.append({"role": "assistant", "content": item["respuesta"]})
    
    def generate():
        respuesta_completa = ""
        
        if modo == "online":
            for pedazo in preguntar_groq_streaming(pregunta, contexto):
                respuesta_completa += pedazo
                yield pedazo
        else:
            for pedazo in preguntar_ollama_streaming(pregunta, contexto):
                respuesta_completa += pedazo
                yield pedazo
        
        if username not in historial_db:
            historial_db[username] = []
        
        historial_db[username].append({
            "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "pregunta": pregunta,
            "respuesta": respuesta_completa,
            "modo": modo
        })
        guardar_json(HISTORIAL_FILE, historial_db)
    
    return StreamingResponse(generate(), media_type="text/plain")

@app.get("/historial/{username}")
def obtener_historial(username: str):
    return cargar_json(HISTORIAL_FILE).get(username, [])

@app.delete("/historial/{username}")
def borrar_historial(username: str):
    historial = cargar_json(HISTORIAL_FILE)
    if username in historial:
        del historial[username]
        guardar_json(HISTORIAL_FILE, historial)
    return {"mensaje": "Historial borrado"}

@app.get("/config")
def obtener_config():
    return {
        "ollama_disponible": False,
        "groq_disponible": GROQ_AVAILABLE,
        "groq_configurado": GROQ_API_KEY.startswith("gsk-") if GROQ_API_KEY else False
    }

@app.get("/")
def root():
    return {"mensaje": "Mi Asistente API está corriendo", "status": "online"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)