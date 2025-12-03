import os
import sys
import json
import requests
import google.generativeai as genai
from colorama import Fore, Style, init

init(autoreset=True)

# CONFIGURATION
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPOSITORY = os.getenv("GITHUB_REPOSITORY")
GITHUB_EVENT_PATH = os.getenv("GITHUB_EVENT_PATH")
api_key = os.getenv("OPENAI_API_KEY") 

if not api_key:
    print(f"{Fore.RED}Error: API Key not found.{Style.RESET_ALL}")
    sys.exit(1)

genai.configure(api_key=api_key)

def read_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        print(f"{Fore.RED}Error: File not found -> {filepath}")
        sys.exit(1)

def post_pr_comment(reason, suggested_fix, model_name):
    print(f"{Fore.CYAN}Attempting to post comment...{Style.RESET_ALL}")

    if not GITHUB_TOKEN:
        print(f"{Fore.RED}❌ FAILED: GITHUB_TOKEN is missing.{Style.RESET_ALL}")
        return

    # DEBUG: Print the event path
    print(f"Reading event from: {GITHUB_EVENT_PATH}")
    
    try:
        with open(GITHUB_EVENT_PATH, 'r') as f:
            event_data = json.load(f)
    except Exception as e:
        print(f"{Fore.RED}❌ FAILED: Could not read event file: {e}{Style.RESET_ALL}")
        return
        
    # Try to find PR number
    pr_number = event_data.get('pull_request', {}).get('number')
    if not pr_number:
        # Fallback for issue comments
        pr_number = event_data.get('issue', {}).get('number')
    
    if not pr_number:
        print(f"{Fore.RED}❌ FAILED: Could not find PR Number in event data.{Style.RESET_ALL}")
        print(f"Event keys found: {list(event_data.keys())}")
        return

    comment_body = f"""
### 🚨 DockDesk: Documentation Drift Detected
**Reason:** {reason}

**Suggested Fix:**
```markdown
{suggested_fix}
```
(Automated by DockDesk running on {model_name}) """

    url = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/issues/{pr_number}/comments"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    resp = requests.post(url, json={"body": comment_body}, headers=headers)

    if resp.status_code == 201:
        print(f"{Fore.GREEN}✅ Comment posted to PR #{pr_number}{Style.RESET_ALL}")
    else:
        print(f"{Fore.RED}❌ GitHub API Error: {resp.status_code} - {resp.text}{Style.RESET_ALL}")

def check_documentation_drift(code_content, doc_content):
    print(f"{Fore.CYAN}🔍 Analyzing with Gemini...{Style.RESET_ALL}")

    models_to_try = ['gemini-2.0-flash', 'gemini-1.5-flash-latest', 'gemini-pro']

    prompt = f"""
You are 'DocuGuard'. Check if the CODE logic contradicts the DOCS.
CRITICAL RULES:
1. Flag CONTRADICTIONS only.
2. Output strictly valid JSON.

--- DOCS ---
{doc_content}
--- CODE ---
{code_content}
"""

    for model_name in models_to_try:
        try:
            model = genai.GenerativeModel(model_name, generation_config={"response_mime_type": "application/json"})
            response = model.generate_content(prompt)
            return json.loads(response.text), model_name
        except Exception:
            continue
            
    sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(1)

    code_path = sys.argv[1]
    doc_path = sys.argv[2]

    result, used_model = check_documentation_drift(read_file(code_path), read_file(doc_path))

    if result.get("has_contradiction"):
        print(f"\n{Fore.RED}🚨 DRIFT DETECTED!{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}Reason:{Style.RESET_ALL} {result.get('reason')}")
        post_pr_comment(result.get("reason"), result.get("suggested_fix"), used_model)
        sys.exit(1)
    else:
        print(f"\n{Fore.GREEN}✅ Accurate.{Style.RESET_ALL}")