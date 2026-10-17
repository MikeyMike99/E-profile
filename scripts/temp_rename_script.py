import os
import json
import urllib.request
import urllib.error
from pathlib import Path

def main():
    root_dir = Path(r"d:\my_programs\e_profile")
    cert_dir = root_dir / "content" / "certifications" / "digital badges and certificates"
    key_file = root_dir / "open router key.txt"
    
    # Check if the directory and key exist
    if not cert_dir.exists():
        print(f"Error: Directory not found - {cert_dir}")
        return
        
    if not key_file.exists():
        print(f"Error: API key file not found - {key_file}")
        return
        
    # Read API key
    with open(key_file, "r") as f:
        content = f.read().strip()
        # Find API_key="sk-or-..." or use first line if it's just the key
        api_key = ""
        for line in content.splitlines():
            if "API_key=" in line:
                api_key = line.split('=', 1)[1].strip('"\'')
                break
            elif line.startswith("sk-or-"):
                api_key = line.strip('"\'')
                break
        
        if not api_key:
            api_key = content.splitlines()[0].strip()
        
    # Gather relative paths
    relative_paths = []
    for path in cert_dir.rglob("*"):
        # We also want to rename directories, so we include them
        rel_path = path.relative_to(cert_dir)
        relative_paths.append(str(rel_path).replace('\\', '/'))
        
    print(f"Found {len(relative_paths)} paths to process.")
    
    # Construct the prompt
    prompt = """
You are a helpful assistant that cleans up file and directory names.
I have a list of file and folder paths from a digital badges and certificates directory.
I need you to propose clean paths for them.
Requirements:
- Fix typos (e.g. "Sisko" -> "Cisco", "meshine learning" -> "Machine Learning", "litracy" -> "Literacy", "funddementals" -> "Fundamentals", "comtia" -> "CompTIA", "credbly" -> "Credly", "inbed" -> "embed", "cognignitive clas" -> "Cognitive Class", "mindfullness" -> "Mindfulness").
- Fix proper casing for acronyms and terms (IBM, CompTIA, Cisco, Linux, Python, LinkedIn, NQF, IT, AI).
- Flag redundant image sizes (e.g., if a file has "(small)", "(Large)", "sizesmall", "sizelarge" in its name, append "_flagged_redundant" before the file extension).
- Keep file extensions exactly as they are (.md, .pdf, .png, etc.).
- Maintain the folder structure depth, just clean the names of the folders and files at each level.
- Output ONLY valid JSON, nothing else. The output must be a JSON object mapping the original relative path to the new clean relative path.
    
Paths to process:
""" + json.dumps(relative_paths, indent=2)

    # Call OpenRouter API
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": "qwen/qwen3-coder:free",
        "messages": [
            {"role": "user", "content": prompt}
        ]
    }
    
    req = urllib.request.Request(url, headers=headers, data=json.dumps(data).encode('utf-8'), method='POST')
    
    try:
        print("Calling OpenRouter API...")
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode('utf-8'))
            content = result['choices'][0]['message']['content']
            
            # Clean up potential markdown formatting around JSON
            content = content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            # Parse it to ensure it's valid JSON
            mapping = json.loads(content)
            
            # Save to proposed_renames.json
            out_file = root_dir / "proposed_renames.json"
            with open(out_file, "w") as f:
                json.dump(mapping, f, indent=4)
                
            print(f"Successfully mapped {len(mapping)} paths.")
            print(f"Saved to {out_file}")
            
    except Exception as e:
        print(f"Error calling API or parsing result: {e}")

if __name__ == '__main__':
    main()
