import os
from google import genai
os.environ["GEMINI_BASE_URL"] = "http://127.0.0.1:5000"
client = genai.Client(api_key="fake")
print("Base URL:", client._api_client.base_url if hasattr(client, '_api_client') else client)
