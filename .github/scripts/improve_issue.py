import os
import requests
import json

def call_gemini_api(title, body):
    # Construye tu prompt aquí, puedes copiar el prompt detallado que usas con Copilot CLI
    instructions = f"""
You are an expert Issue Quality Enhancer for a public GitHub repo.
Your job is to take a newly opened issue and improve its quality so it is clear, detailed, well-structured, and consistent with the best open source standards.

Rules:
- Start title with relevant emoji (🐛 for bugs, ✨ for features, etc.), 5-12 words after emoji, imperative mood.
- Enhance body: Structure as bug report or feature template, use emoji headers, add code references if present, and append a credit footer (original author).
- Language: English only; translate if needed.
- DO NOT change technical meaning. Minimal change if well structured.
- Provide output as JSON with `title` and `body`.

Original Details:
- Title: {title}
- Body: {body}
"""
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash-preview:generateContent"
    headers = {"Content-Type": "application/json"}
    data = {
        "contents": [{"parts": [{"text": instructions}]}]
    }
    params = {"key": os.environ["GEMINI_API_KEY"]}
    r = requests.post(url, json=data, params=params, headers=headers)
    r.raise_for_status()
    raw = r.json()
    try:
        # Gemini responde en texto plano, busca el JSON dentro del texto
        gemini_text = raw["candidates"][0]["content"]["parts"][0]["text"]
        # Extraer JSON delimitado con ``` o { ... }
        start = gemini_text.find('{')
        end = gemini_text.rfind('}')
        if start >= 0 and end > start:
            extracted = gemini_text[start:end+1]
            improved = json.loads(extracted)
        else:
            # Alternativamente solo reescribe el title/body si no viene JSON
            improved = {"title": title, "body": f"{gemini_text}\n\n---\n> ✍️ *This issue was automatically enhanced by Gemini. Original author: @{os.environ['ISSUE_AUTHOR']}*"}
    except Exception as e:
        improved = {"title": title, "body": body}
    return improved

def update_issue(repo, issue_number, token, title, body):
    url = f"https://api.github.com/repos/{repo}/issues/{issue_number}"
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github+json"}
    data = {"title": title, "body": body}
    r = requests.patch(url, json=data, headers=headers)
    r.raise_for_status()

def main():
    repo = os.environ["REPO"]
    issue_number = os.environ["ISSUE_NUMBER"]
    token = os.environ["GH_TOKEN"]
    title = os.environ["ISSUE_TITLE"]
    body = os.environ["ISSUE_BODY"]
    print(f"Enhancing issue #{issue_number}...")

    improved = call_gemini_api(title, body)
    update_issue(repo, issue_number, token, improved["title"], improved["body"])
    print(f"Issue #{issue_number} enhanced with Gemini.")

if __name__ == "__main__":
    main()