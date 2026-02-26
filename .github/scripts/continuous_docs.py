import os
import requests
import json
import subprocess

def get_pr_diff(repo, pr_number, token):
    url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3.diff"
    }
    r = requests.get(url, headers=headers)
    r.raise_for_status()
    return r.text

def call_gemini_api(diff_text, pr_title, pr_author):
    instructions = f"""
You are an expert Continuous Documentation assistant.
Analyze the following pull request code changes and detect documentation drift.
Provide updated content for any README, docs, or code files (JSDoc/docstrings) that need updates to match the new code behavior.

PULL REQUEST DETAILS:
- Title: {pr_title}
- Author: @{pr_author}

DIFF:
{diff_text[:15000]}

Respond ONLY with a valid JSON array containing the files that need to be updated. Example format:
[
  {{
    "file_path": "README.md",
    "updated_content": "Full new content of the file..."
  }}
]
If no documentation drift is found, return an empty array `[]`. Do not include any HTML formatting, do not wrap in ```json, just output the plain text JSON array starting with `[` and ending with `]`.
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
            extracted = gemini_text[start:end+1]
            return json.loads(extracted)
        return []
    except Exception as e:
        print(f"Error parsing Gemini response: {e}")
        return []

def comment_on_pr(repo, pr_number, token, body):
    url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json"
    }
    requests.post(url, json={"body": body}, headers=headers)

def main():
    repo = os.environ["REPO"]
    pr_number = os.environ["PR_NUMBER"]
    token = os.environ["GH_TOKEN"]
    pr_title = os.environ.get("PR_TITLE", "")
    pr_author = os.environ.get("PR_AUTHOR", "")

    print(f"Analyzing PR #{pr_number} for documentation drift...")
    diff_text = get_pr_diff(repo, pr_number, token)
    
    if not diff_text.strip():
        print("No diff found.")
        comment_on_pr(repo, pr_number, token, "📚 **Docs are in sync!** No documentation drift detected (empty diff). 👏")
        return

    updates = call_gemini_api(diff_text, pr_title, pr_author)
    
    if not updates:
        print("No documentation drift detected.")
        comment_on_pr(repo, pr_number, token, f"📚 **Docs are in sync!** No documentation drift detected for this PR. Great job @{pr_author}! 👏")
        return

    updated_files = []
    for update in updates:
        file_path = update.get("file_path")
        content = update.get("updated_content")
        if file_path and content:
            if not os.path.exists(file_path):
                print(f"File {file_path} doesn't exist, skipping to avoid unintended new files.")
                continue
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(content)
                updated_files.append(file_path)
                print(f"Updated {file_path}")
            except Exception as e:
                print(f"Could not update {file_path}: {e}")

    if updated_files:
        # Commit changes
        subprocess.run(["git", "config", "user.name", "github-actions[bot]"], check=True)
        subprocess.run(["git", "config", "user.email", "github-actions[bot]@users.noreply.github.com"], check=True)
        for f in updated_files:
            subprocess.run(["git", "add", f], check=True)
        subprocess.run(["git", "commit", "-m", "📚 docs: update documentation to match code changes"], check=True)
        subprocess.run(["git", "push"], check=True)

        # Comment on PR
        files_list = "\n".join([f"- `{f}`" for f in updated_files])
        comment = (
            f"📚 **Documentation updated!**\n\n"
            f"I detected documentation drift and pushed a commit to fix it:\n{files_list}\n\n"
            f"Please review the changes and adjust if needed.\n\n"
            f"---\n> 🤖 *Auto-updated by Gemini Continuous Documentation*"
        )
        comment_on_pr(repo, pr_number, token, comment)
    else:
        comment_on_pr(repo, pr_number, token, f"📚 **Docs are in sync!** No documentation drift detected for this PR. Great job @{pr_author}! 👏")

if __name__ == "__main__":
    main()
