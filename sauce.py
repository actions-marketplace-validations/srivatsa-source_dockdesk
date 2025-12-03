import os
import sys
import json
import requests
import google.generativeai as genai
from colorama import Fore, Style, init

init(autoreset=True)

# ---------------------------------------------------------
# 1. CONFIGURATION
# ---------------------------------------------------------
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPOSITORY = os.getenv("GITHUB_REPOSITORY")
GITHUB_EVENT_PATH = os.getenv("GITHUB_EVENT_PATH")

# Read API Key
api_key = os.getenv("OPENAI_API_KEY") 
if not api_key:
    print(f"{Fore.RED}Error: API Key not found.{Style.RESET_ALL}")
    sys.exit(1)

# Configure Gemini
genai.configure(api_key=api_key)

# ---------------------------------------------------------
# 2. HELPER FUNCTIONS
# ---------------------------------------------------------
def read_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        print(f"{Fore.RED}Error: File not found -> {filepath}")
        sys.exit(1)

def post_pr_comment(reason, suggested_fix):
    if not GITHUB_TOKEN or not GITHUB_REPOSITORY or not GITHUB_EVENT_PATH:
        print(f"{Fore.YELLOW}Skipping comment: Missing GitHub context.{Style.RESET_ALL}")
        return

    try:
        with open(GITHUB_EVENT_PATH, 'r') as f:
            event_data = json.load(f)
            pr_number = event_data.get('pull_request', {}).get('number') or \
                        event_data.get('issue', {}).get('number')
            if not pr_number: return
    except Exception:
        return

    comment_body = f"""
### 🚨 DockDesk: Documentation Drift Detected
**Reason:** {reason}

**Suggested Fix:**
```markdown
{suggested_fix}
```
"""

    url = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/issues/{pr_number}/comments"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    requests.post(url, json={"body": comment_body}, headers=headers)
    print(f"{Fore.GREEN}✅ Comment posted to PR #{pr_number}{Style.RESET_ALL}")

def check_documentation_drift(code_content, doc_content):
    # FIX: Use 'gemini-1.5-flash-latest' which is often more reliable
    model = genai.GenerativeModel('gemini-1.5-flash-latest',
        generation_config={"response_mime_type": "application/json"})

    prompt = f"""
You are 'DocuGuard'. Check if the CODE logic contradicts the DOCS.

CRITICAL RULES:
1. Flag CONTRADICTIONS only (Code says X, Docs say Y).
2. Ignore missing details.
3. Output strictly valid JSON: {{"has_contradiction": true/false, "reason": "...", "suggested_fix": "..."}}

--- DOCS ---
{doc_content}

--- CODE ---
{code_content}
"""

    try:
        response = model.generate_content(prompt)
        return json.loads(response.text)
    except Exception as e:
        print(f"{Fore.RED}Gemini Error: {e}{Style.RESET_ALL}")
        # Fallback for debugging: Print available models if this fails again
        # for m in genai.list_models(): print(m.name)
        sys.exit(1)

# ---------------------------------------------------------
# 3. MAIN EXECUTION
# ---------------------------------------------------------
if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(1)

    code_path = sys.argv[1]
    doc_path = sys.argv[2]

    code_text = read_file(code_path)
    doc_text = read_file(doc_path)

    result = check_documentation_drift(code_text, doc_text)

    if result.get("has_contradiction"):
        print(f"\n{Fore.RED}🚨 DRIFT DETECTED!{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}Reason:{Style.RESET_ALL} {result.get('reason')}")
        
        post_pr_comment(result.get("reason"), result.get("suggested_fix"))
        
        sys.exit(1)
    else:
        print(f"\n{Fore.GREEN}✅ Accurate.{Style.RESET_ALL}")