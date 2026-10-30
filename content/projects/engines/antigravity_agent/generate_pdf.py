import sys
try:
    from markdown_pdf import MarkdownPdf, Section
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "markdown-pdf"])
    from markdown_pdf import MarkdownPdf, Section

pdf = MarkdownPdf(toc_level=2)
content = open("C:/Users/michael/Documents/DevCore/README.md", "r", encoding="utf-8").read()
pdf.add_section(Section(content, toc=False))
pdf.save("C:/Users/michael/Documents/DevCore/README.pdf")
