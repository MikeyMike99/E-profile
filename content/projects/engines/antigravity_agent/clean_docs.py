import os
import re

docs_dir = 'docs/reference_docs'
for filename in os.listdir(docs_dir):
    if not filename.endswith('.md') or 'Clean' in filename:
        continue
    
    filepath = os.path.join(docs_dir, filename)
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Remove HTML tags (like <img...>, <p align...>, <br>, <div>, etc.)
    content = re.sub(r'<[^>]+>', '', content)
    
    # Remove Markdown images ![alt](url)
    content = re.sub(r'!\[.*?\]\(.*?\)', '', content)
    
    # Remove complex markdown badges (nested link/image tags)
    content = re.sub(r'\[!\[.*?\]\(.*?\)\]\(.*?\)', '', content)
    
    # Remove raw markdown links but keep the text: [Text](url) -> Text
    # We will just remove the url part to make reading cleaner
    content = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', content)
    
    # Clean up excessive empty lines caused by deletions
    content = re.sub(r'\n{3,}', '\n\n', content)

    clean_filepath = os.path.join(docs_dir, filename.replace('.md', '_Clean.md'))
    with open(clean_filepath, 'w', encoding='utf-8') as f:
        f.write(content)

print("Documentation cleaned!")
