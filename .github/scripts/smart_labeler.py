import os
import requests
import json

def get_pr_diff(repo, pr_number, token):
    url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}"
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3.diff"}
    r = requests.get(url, headers=headers)
    r.raise_for_status()
    return r.text

def call_gemini(diff_text, pr_title):
    instructions = f"""
You are a Smart Labeler for GitHub Pull Requests.
Analyze the following PR title and diff, and decide which labels apply to this PR.
Choose ONLY from these common labels:
- "🐛 bug"
- "✨ enhancement"
- "📖 documentation"
- "♻️ refactor"
- "🧪 test"
- "🔧 config"
- "🚀 deployment"
- "🔒 security"

PR Title: {pr_title}
DIFF:
{diff_text[:15000]}

Respond ONLY with a valid JSON array of strings containing the exact labels. Example:
["🐛 bug", "🧪 test"]
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

def add_labels_to_pr(repo, pr_number, token, labels):
    url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/labels"
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    data = {"labels": labels}
    r = requests.post(url, json=data, headers=headers)
    r.raise_for_status()

def main():
    repo = os.environ["REPO"]
    pr_number = os.environ["PR_NUMBER"]
    token = os.environ["GH_TOKEN"]
    pr_title = os.environ.get("PR_TITLE", "")

    diff_text = get_pr_diff(repo, pr_number, token)
    if not diff_text.strip():
        print("No diff found, skipping labels.")
        return

    labels = call_gemini(diff_text, pr_title)
    if not labels:
        print("No labels suggested.")
        return

    print(f"Adding labels: {labels}")
    add_labels_to_pr(repo, pr_number, token, labels)
    print("✅ Smart labeling completed.")

if __name__ == "__main__":
    main()
