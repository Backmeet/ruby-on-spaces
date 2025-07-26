import os
import requests
import base64
import subprocess

# Base GitHub URLs
repo = "Backmeet/ruby-on-spaces"
contents_api = f"https://api.github.com/repos/{repo}/contents/"

# Get top-level directory contents
response = requests.get(contents_api)
contents = response.json()

# Find versioned folders starting with "ver"
versions = {}
for item in contents:
    if item["type"] == "dir" and item["name"].startswith("ver"):
        versions[item["name"]] = item["url"]

# Ask user which version to install
print("What version of Ruby on Spaces should be installed?")
for ver in versions:
    print(f"   {ver}")
ver = input(": ").strip()

if ver not in versions:
    print(f"Version {ver} does not exist. Try installing again.")
    exit(1)

# Get contents of selected version folder
response = requests.get(versions[ver])
folder_contents = response.json()

# Find interpret.py
interpret_url = None
for item in folder_contents:
    if item["name"] == "interpret.py":
        interpret_url = item["url"]
        break

if not interpret_url:
    print("Interpret.py not found in selected version.")
    exit(1)

# Download and decode the file
response = requests.get(interpret_url)
file_data = response.json()
encoded_content = file_data["content"]

# Decode base64 content
decoded_bytes = base64.b64decode(encoded_content)
code_text = decoded_bytes.decode("utf-8")

# Ask for command alias
cmdLineName = input("What alias should the command line interpreter have?: ").strip()

# Setup installation path
scripts_dir = os.path.expandvars(r"%USERPROFILE%\Scripts")
os.makedirs(scripts_dir, exist_ok=True)

target_path = os.path.join(scripts_dir, f"{cmdLineName}.py")
with open(target_path, "w", encoding="utf-8") as f:
    f.write(code_text)

# Add the directory (not the file) to PATH
# Avoid duplicate PATH entries
if scripts_dir.lower() not in os.environ["PATH"].lower():
    subprocess.run(["setx", "PATH", f"%PATH%;{scripts_dir}"], shell=True)
    print("[+] Added Scripts directory to PATH")
else:
    print("[✓] Scripts directory already in PATH")

print(f"[✓] Installed as '{cmdLineName}.py'")
print(f"Open a new terminal and run: {cmdLineName}.py <path>")
