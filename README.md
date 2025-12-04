<div align="center">

# 🛡️ DockDesk

<a href="https://git.io/typing-svg">
  <img src="https://readme-typing-svg.demolab.com?font=Fira+Code&weight=600&size=22&pause=1000&color=2786F7&center=true&vCenter=true&width=500&lines=Stop+drifting.;Stop+lying+to+your+team.;AI-powered+documentation+auditing." alt="Typing SVG" />
</a>

> **The AI Auditor that ensures your Code never contradicts your Documentation.**

<p align="center">
  <a href="#-see-it-in-action">View Demo</a> •
  <a href="#-setup">Installation</a> •
  <a href="#-how-it-works">How It Works</a>
</p>


<p align="center">
<img src="https://img.shields.io/badge/AI%20Model-Gemini%202.0%20Flash-8E74F1?style=for-the-badge&logo=google&logoColor=white" alt="AI Model">
<img src="https://img.shields.io/github/actions/workflow/status/srivatsa-source/dockdesk/main.yml?style=for-the-badge&label=BUILD" alt="Build Status">
<img src="https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge" alt="License">
</p>

</div>

---

## 🎥 See it in Action

Docs say one thing. Code does another. **DockDesk catches it before you merge.**

<div align="center">
  <img src="demo.gif" alt="DockDesk Demo Animation" width="800" style="border-radius: 10px; box-shadow: 0px 0px 20px rgba(0,0,0,0.2);">
</div>

<br>

## 💀 The Problem: "Knowledge Drift"

Developers write code faster than they write documentation.

1.  ❌ You update the code logic to require admin privileges.
2.  ❌ You forget to update the `README.md` which says it's public.
3.  🔥 **Result:** Consumers of your API get frustrated, and onboarding new devs becomes a nightmare.

## ⚡ The Solution: Active Compliance

DockDesk is not a static analyzer looking for keywords. It's an AI agent that understands **intent**.

It sits in your CI/CD pipeline and audits every Pull Request using **Google Gemini 2.0**.

| Feature | Description |
| :--- | :--- |
| 👀 **Reads** | Scans your logic changes (`.js`, `.py`, etc.) and your docs (`.md`). |
| 🧠 **Thinks** | Detects semantic contradictions (e.g., "Age 18+ vs Admin Only"). |
| 🗣️ **Speaks** | Blocks the PR and comments directly with the exact fix required. |

---

## 🧠 How It Works

It flows automatically whenever a developer tries to merge code.

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#2786F7', 'edgeLabelBackground':'#ffffff', 'tertiaryColor': '#f4f4f4'}}}%%
graph TD
    A[👨‍💻 Dev Pushes Code] -->|Pull Request| B(🚀 GitHub Action Triggers);
    B --> C{📁 DockDesk Reads Files};
    C -->|Code & Docs| D[🤖 Gemini 2.0 AI Analysis];
    D -->|Contradiction Found?| E{Drift Detected?};
    E -- YES --> F[❌ Block PR & Post Comment];
    E -- NO --> G[✅ Pass Checks];

    style F fill:#ffcccc,stroke:#ff0000,stroke-width:2px,color:red
    style G fill:#ccffcc,stroke:#00ff00,stroke-width:2px,color:green
```

## 📦 Setup

Add this workflow to your repository at `.github/workflows/dockdesk.yml`:

```yaml
name: DockDesk Audit
on: [pull_request]

jobs:
  audit:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: write # Required for commenting
    steps:
      - uses: actions/checkout@v3
      - name: Run AI Auditor
        # Replace with your version (or @main for latest)
        uses: srivatsa-source/dockdesk@main
        with:
          # Your Gemini or OpenAI Key
          openai_api_key: ${{ secrets.OPENAI_API_KEY }}
          github_token: ${{ secrets.GITHUB_TOKEN }}
          # The files to compare
          code_file: 'src/auth.js'
          doc_file: 'docs/API.md'
```

<div align="center">

Built with ❤️ + 🤖 by DockDesk

</div>
