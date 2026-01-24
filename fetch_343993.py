import urllib.request, json
TOKEN = "da4c33f6-42de-4f77-afb7-e7758a8431ca"
headers = {"Authorization": f"Token {TOKEN}", "User-Agent": "Mozilla/5.0"}

def download(url, filename):
    print(f"Downloading {url}...")
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            data = resp.read().decode()
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(data)
            print(f"Saved to {filename}")
    except Exception as e:
        print(f"Failed to download {url}: {e}")

download("https://eu1.make.com/api/v2/scenarios/343993", "scenario_343993_meta.json")
download("https://eu1.make.com/api/v2/scenarios/343993/blueprint", "scenario_343993_blueprint.json")
