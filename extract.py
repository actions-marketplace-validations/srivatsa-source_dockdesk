import subprocess

res = subprocess.run(["git", "show", "5dd21ae:dockdesk/cli.py"], capture_output=True)
content = res.stdout.decode("utf-8")

with open("extracted.py", "w", encoding="utf-8") as f:
    f.write(content)
