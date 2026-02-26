import os
import requests
import json

def get_pr_diff(repo, pr_number, token):
    url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}"
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3.diff"}
    r = requests.get(url, headers=headers)
    r.raise_for_status()
    return r.text

def get_issue(repo, issue_number, token):
    url = f"https://api.github.com/repos/{repo}/issues/{issue_number}"
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    r = requests.get(url, headers=headers)
    r.raise_for_status()
    return r.json()

def call_gemini(context, title, item_type):
    if item_type == "pull_request":
        prompt_context = f"PR Title: {title}\nDIFF:\n{context[:15000]}"
    else:
        prompt_context = f"Issue Title: {title}\nISSUE BODY:\n{context[:15000]}"

    instructions = f"""
You are a Smart Labeler for GitHub {item_type.replace('_', ' ').title()}s.
Analyze the following title and content, and decide which labels apply.
Choose ONLY from these common labels:
- "🐛 bug"
- "✨ enhancement"
- "📖 documentation"
- "♻️ refactor"
- "🧪 test"
- "🔧 config"
- "🚀 deployment"
- "🔒 security"
- "❓ help wanted"
- "💬 discussion"

{prompt_context}

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

def add_labels_to_item(repo, item_number, token, labels):
    url = f"https://api.github.com/repos/{repo}/issues/{item_number}/labels"
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    data = {"labels": labels}
    r = requests.post(url, json=data, headers=headers)
    r.raise_for_status()

def main():
    repo = os.environ["REPO"]
    item_number = os.environ.get("ITEM_NUMBER")
    token = os.environ["GH_TOKEN"]
    item_title = os.environ.get("ITEM_TITLE", "")
    item_body = os.environ.get("ITEM_BODY", "")
    item_type = os.environ.get("ITEM_TYPE", "pull_request")

    if not item_number:
        print("Error: ITEM_NUMBER or PR_NUMBER must be provided.")
        return

    print(f"Analyzing {item_type} #{item_number}: {item_title}")

    context = ""
    if item_type == "pull_request":
        try:
            context = get_pr_diff(repo, item_number, token)
        except Exception as e:
            print(f"Could not get PR diff: {e}")
    else:
        if item_body:
            context = item_body
        else:
            try:
                issue_data = get_issue(repo, item_number, token)
                context = issue_data.get("body", "") or "No description provided."
            except Exception as e:
                print(f"Could not get Issue data: {e}")

    if not context.strip() and item_type == "pull_request":
        print("No diff found, skipping labels.")
        return

    labels = call_gemini(context, item_title, item_type)
    if not labels:
        print("No labels suggested.")
        return

    print(f"Adding labels: {labels}")
    add_labels_to_item(repo, item_number, token, labels)
    print("✅ Smart labeling completed.")

if __name__ == "__main__":
    main()
