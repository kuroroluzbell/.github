import os
import requests
import json

def get_labels(repo, token):
    url = f"https://api.github.com/repos/{repo}/labels"
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    r = requests.get(url, headers=headers)
    r.raise_for_status()
    return r.json()

def call_gemini(labels):
    instructions = f"""
You are a Label Beautifier.
I will give you a list of current GitHub labels. 
Propose a beautified version for each label (add relevant emoji at the start, english description, meaningful color hex code without #).
Return explicitly a JSON array of objects with keys: 'original_name', 'new_name', 'description', 'color'.

Current labels:
{json.dumps(labels, indent=2)}

Format:
[
  {{ "original_name": "bug", "new_name": "🐛 bug", "description": "Something isn't working", "color": "d73a4a" }}
]
Respond ONLY with the plain JSON array.
"""
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash-preview:generateContent"
    headers = {"Content-Type": "application/json"}
    data = {"contents": [{"parts": [{"text": instructions}]}]}
    params = {"key": os.environ["GEMINI_API_KEY"]}
    r = requests.post(url, json=data, params=params, headers=headers)
    r.raise_for_status()
    raw = r.json()
    try:
        gemini_text = raw["candidates"][0]["content"]["parts"][0]["text"]
        start = gemini_text.find('[')
        end = gemini_text.rfind(']')
        if start >= 0 and end > start:
            return json.loads(gemini_text[start:end+1])
    except Exception as e:
        print(f"Error parsing Gemini: {e}")
    return []

def update_label(repo, token, original_name, new_name, description, color):
    # GitHub label update
    url = f"https://api.github.com/repos/{repo}/labels/{original_name}"
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    data = {"new_name": new_name, "description": description[:100], "color": color}
    r = requests.patch(url, json=data, headers=headers)
    if r.status_code == 200:
        print(f"Updated '{original_name}' -> '{new_name}'")
    else:
        print(f"Failed to update '{original_name}': {r.text}")

def main():
    repo = os.environ["REPO"]
    token = os.environ["GH_TOKEN"]
    dry_run = os.environ.get("DRY_RUN", "false").lower() == "true"

    labels = get_labels(repo, token)
    simplified_labels = [{"name": l["name"], "description": l["description"], "color": l["color"]} for l in labels]
    
    plan = call_gemini(simplified_labels)
    if not plan:
        print("No changes proposed.")
        return

    print("Change Plan:")
    for item in plan:
        print(f" - {item['original_name']} -> {item['new_name']} ({item['color']}) | {item['description']}")

    if dry_run:
        print("DRY RUN mode enabled. No changes applied.")
        return

    print("Applying changes...")
    for item in plan:
        if item['original_name'] != item['new_name'] or True: # Force update for description/color
            update_label(repo, token, item['original_name'], item['new_name'], item['description'], item['color'])
            
    print("✅ Label beautification completed.")

if __name__ == "__main__":
    main()
