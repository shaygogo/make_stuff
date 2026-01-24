import urllib.request, json
TOKEN = "da4c33f6-42de-4f77-afb7-e7758a8431ca"
headers = {"Authorization": f"Token {TOKEN}", "User-Agent": "Mozilla/5.0"}
# List of organizations retrieved from previous step
org_ids = [680992, 681392, 593202, 39433, 415835, 54119, 243933, 4459087, 1125104, 331002, 681038, 8538, 318339, 26618, 395713, 214316]

print("Fetching Teams...")
for oid in org_ids:
    # Most organizations are on eu1, but some (like Localista and Mr Make) are on eu2
    base = "https://eu1.make.com/api/v2" if oid not in [4459087, 1125104] else "https://eu2.make.com/api/v2"
    url = f"{base}/teams?organizationId={oid}"
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())
            for t in data.get('teams', []):
                print(f"Org: {oid} | Team: {t['id']} | Name: {t['name']} | Zone: {base}")
    except Exception as e:
        # Silently skip errors for organizations where the token might not have access
        continue
