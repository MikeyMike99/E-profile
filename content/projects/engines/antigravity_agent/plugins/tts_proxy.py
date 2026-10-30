import requests
import json
import os

def generate_audio(text: str, ui_config_path: str):
    """
    Acts as the API Proxy for TTS generation. 
    Reads the configuration dynamically and makes the outbound request.
    """
    try:
        with open(ui_config_path, 'r') as f:
            config = json.load(f)
    except Exception as e:
        return {"error": "Failed to load configuration"}, 500

    tts_config = config.get("tts_engine", {})
    if not tts_config.get("enabled"):
        return {"error": "TTS Engine is disabled in configuration"}, 403
        
    api_key = tts_config.get("api_key")
    voice_id = tts_config.get("voice_id")
    
    if not api_key:
        return {"error": "TTS API Key is missing"}, 400

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": api_key
    }
    
    data = {
        "text": text,
        "model_id": "eleven_monolingual_v1",
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75
        }
    }
    
    try:
        # We enforce a strict timeout to prevent thread blocking (The Reaper protocol)
        response = requests.post(url, json=data, headers=headers, timeout=10)
        
        if response.status_code == 200:
            return response.content, 200
        else:
            return {"error": f"ElevenLabs API Error: {response.status_code}"}, response.status_code
            
    except requests.exceptions.RequestException as e:
        return {"error": f"Connection to TTS proxy failed: {str(e)}"}, 502