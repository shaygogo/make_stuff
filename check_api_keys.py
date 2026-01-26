
import os
import json
import urllib.request
from dotenv import load_dotenv

load_dotenv()

token = os.getenv('PIPEDRIVE_API_TOKEN')
url = f"https://api.pipedrive.com/v1/dealFields?api_token={token}"

try:
    with urllib.request.urlopen(url) as resp:
        data = json.loads(resp.read().decode('utf-8'))
        if data.get('success'):
             first_field = data['data'][0]
             print("Keys in first field:", list(first_field.keys()))
             print("Has 'key'?", 'key' in first_field)
             print("Has 'field_code'?", 'field_code' in first_field)
except Exception as e:
    print(e)
