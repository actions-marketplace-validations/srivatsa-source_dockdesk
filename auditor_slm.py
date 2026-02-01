import hashlib
import requests
import json
import os
import sys
import re
import argparse
from colorama import Fore, Style, init

# Initialize Colorama with autoreset to avoid bleeding colors
init(autoreset=True)

class NeuralAuditor:
    def __init__(self, ci_mode=False):
        self.ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434/api/chat")
        self.model = os.getenv("MODEL_NAME", "qwen2.5-coder:3b")
        self.temperature = 0.1 # Strict deterministic output
        self.ci_mode = ci_mode
        
    def log_info(self, text):
        print(f"{Fore.CYAN}[*] {text}{Style.RESET_ALL}")

    def log_success(self, text):
        print(f"{Fore.GREEN}[+] {text}{Style.RESET_ALL}")
        
    def log_fail(self, text):
        print(f"{Fore.RED}[!] {text}{Style.RESET_ALL}")

    def log_header(self, text):
        print(f"\n{Fore.MAGENTA}=== {text} ==={Style.RESET_ALL}")

    def calculate_merkle_hash(self, content):
        """
        Calculates SHA-256 hash to act as a Merkle Leaf Node.
        """
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    def clean_json(self, raw_text):
        """
        Robust JSON extraction. approaches:
        1. Parse directly.
        2. Extract content between ```json ... ```.
        3. Extract content between first { and last }.
        4. Fallback regex parsing for malformed JSON (common with 3B models).
        """
        try:
            return json.loads(raw_text)
        except json.JSONDecodeError:
            pass

        # Attempt to find markdown json block
        match = re.search(r"```json\s*(.*?)\s*```", raw_text, re.DOTALL)
        if match:
            text = match.group(1)
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                pass
        
        # Attempt to find raw braces
        match = re.search(r"(\{.*\})", raw_text, re.DOTALL)
        if match:
            text = match.group(1)
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                pass
        
        # Fallback: Regex Scraping for "Broken" JSON
        # This handles cases where the model puts real newlines inside strings
        fallback = {}
        
        # Extract Status
        s_m = re.search(r'"status":\s*"(\w+)"', raw_text)
        if s_m: fallback["status"] = s_m.group(1)
        
        # Extract Risk
        r_m = re.search(r'"risk":\s*"(\w+)"', raw_text)
        if r_m: fallback["risk"] = r_m.group(1)

        # Extract Requirements (Simple single line assumption or lazy dotall)
        c_m = re.search(r'"code_requirement":\s*"(.*?)"', raw_text, re.DOTALL)
        if c_m: fallback["code_requirement"] = c_m.group(1)
        
        d_m = re.search(r'"doc_requirement":\s*"(.*?)"', raw_text, re.DOTALL)
        if d_m: fallback["doc_requirement"] = d_m.group(1)
        
        # Extract Fix (Heuristic: grab everything after "fix": until the closing brace)
        # We look for "fix": ... and grab until the last quote before the final }
        # This is tricky, so we take a greedy approach from "fix": " until " \n }
        f_m = re.search(r'"fix":\s*"(.*)"\s*\}\s*$', raw_text, re.DOTALL) 
        if not f_m:
             # Try looser match if the closing quote is missing or messy
             f_m = re.search(r'"fix":\s*"?([\s\S]*?)"?\s*\}\s*$', raw_text, re.DOTALL)
        
        if f_m:
            fallback["fix"] = f_m.group(1)
        
        if "status" in fallback:
            return fallback

        return None

    def query_model(self, prompt, system_role):
        """
        Sends request to Ollama Chat API.
        """
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_role},
                {"role": "user", "content": prompt}
            ],
            "stream": False,
            "options": {
                "temperature": self.temperature
            }
        }
        
        try:
            response = requests.post(self.ollama_url, json=payload, timeout=120)
            response.raise_for_status()
            return response.json().get("message", {}).get("content", "")
        except requests.exceptions.ConnectionError:
            self.log_fail(f"Could not connect to {self.ollama_url}. Is Ollama running?")
            sys.exit(1)
        except Exception as e:
            self.log_fail(f"Model query failed: {e}")
            sys.exit(1)

    def save_report(self, result):
        """Generates a Markdown report for CI/CD pipelines."""
        status_icon = "❌" if result.get("status") == "FAIL" else "✅"
        report = f"""# 🛡️ DockDesk Integrity Report
**Status:** {status_icon} {result.get('status')}
**Risk Level:** {result.get('risk')}

## 🔍 Logic Analysis
| Scope | Detected Logic |
|-------|----------------|
| **Code** | `{result.get('code_requirement')}` |
| **Docs** | `{result.get('doc_requirement')}` |

## 🛠️ Proposed Fix
*(Applied automatically if running in fix-mode, otherwise suggestion below)*

```markdown
{result.get('fix')}
```

> Generated by DockDesk Neural Auditor ({self.model})
"""
        try:
            with open("audit_report.md", "w", encoding="utf-8") as f:
                f.write(report)
            self.log_info("Report saved to audit_report.md")
        except Exception as e:
            self.log_fail(f"Could not save report: {e}")

    def run_audit(self):
        self.log_header(f"DockDesk Neural Auditor ({self.model}){' [CI MODE]' if self.ci_mode else ''}")
        
        # 1. Load Artifacts
        try:
            with open("auth.py", "r", encoding="utf-8") as f:
                code_content = f.read()
            with open("README.md", "r", encoding="utf-8") as f:
                doc_content = f.read()
        except FileNotFoundError:
            self.log_fail("Missing 'auth.py' or 'README.md'. Cannot proceed.")
            sys.exit(1)

        # 2. Merkle Hashing (Drift Detection)
        code_hash = self.calculate_merkle_hash(code_content)
        self.log_success(f"Merkle Hash (auth.py): {code_hash}")

        # 3. Construct Chain-of-Thought Prompt
        system_prompt = """
        You are a Lead Security Auditor.
        Task: specific logic check between Code and Documentation.
        
        Follow this thought process:
        1. EXTRACT: What authentication logic/param does the CODE require? (e.g. 'email', 'user_id', 'password')
        2. EXTRACT: What authentication logic/param does the DOCS claim is used?
        3. COMPARE: Do they match? (Ignore variable naming conventions, focus on the logic).
        
        Your output must be a valid JSON object ONLY. Do not write introductory text.
        IMPORTANT: formatting rules:
        1. "fix" value MUST be a single line string with all newlines escaped as \\n.
        2. Do not include real line breaks inside the JSON string values.
        
        Format:
        {
            "code_requirement": "summary of code logic",
            "doc_requirement": "summary of doc claims",
            "status": "PASS" or "FAIL",
            "risk": "HIGH" or "LOW",
            "fix": "Full markdown text of the corrected README.md (only if FAIL, else null)"
        }
        """
        
        user_prompt = f"""
        DATA:
        --- CODE (auth.py) ---
        {code_content}
        --- DOCS (README.md) ---
        {doc_content}
        """

        self.log_info(f"Analyzing Logic Consistency...")
        raw_response = self.query_model(user_prompt, system_prompt)
        
        # 4. Parse & React
        result = self.clean_json(raw_response)
        
        if not result:
            self.log_fail("Failed to parse model response.")
            print(f"{Fore.YELLOW}Raw Output:\n{raw_response}{Style.RESET_ALL}")
            return

        status = result.get("status", "UNKNOWN")
        risk = result.get("risk", "UNKNOWN")
        
        if status == "FAIL":
            self.log_header("❌ INTEGRITY VIOLATION DETECTED ❌")
            print(f"{Fore.RED}Risk Level: {risk}")
            print(f"Code Logic: {result.get('code_requirement')}")
            print(f"Doc Claim:  {result.get('doc_requirement')}{Style.RESET_ALL}")
            
            # Save Report for CI
            if self.ci_mode:
                self.save_report(result)
                print(f"::error::Integrity check failed. See audit_report.md for details.")
                sys.exit(1)

            fix_content = result.get("fix")
            if fix_content:
                print(f"\n{Fore.CYAN}Proposed Fix Preview:{Style.RESET_ALL}")
                print("-" * 40)
                print(fix_content[:200] + "..." if len(fix_content) > 200 else fix_content)
                print("-" * 40)
                
                choice = input(f"\n{Fore.YELLOW}[?] Apply Fix to README.md? (y/n): {Style.RESET_ALL}")
                if choice.lower() == 'y':
                    with open("README.md", "w", encoding="utf-8") as f:
                        f.write(fix_content)
                    self.log_success("Patch applied successfully.")
                else:
                    self.log_info("Patch skipped.")
            else:
                self.log_fail("No fix provided by model.")
                
        elif status == "PASS":
            self.log_success("Integrity Check Passed. Logic is consistent.")
            if self.ci_mode:
                self.save_report(result)
        else:
            self.log_fail(f"Ambiguous Result: {status}")
            if self.ci_mode:
                sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='DockDesk Neural Auditor')
    parser.add_argument('--ci', action='store_true', help='Run in CI/CD mode (non-interactive, exit codes)')
    args = parser.parse_args()

    auditor = NeuralAuditor(ci_mode=args.ci)
    auditor.run_audit()
