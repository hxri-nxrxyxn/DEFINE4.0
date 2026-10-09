import re
from bs4 import BeautifulSoup
from markdownify import markdownify as md

with open('/tmp/gemini_dump.html', 'r', encoding='utf-8', errors='ignore') as f:
    content = f.read()

soup = BeautifulSoup(content, 'html.parser')
mc = soup.find('message-content')

# Replace math-block with $$...$$
for el in mc.find_all(attrs={'class': lambda c: c and 'math-block' in str(c)}):
    math_content = el.get('data-math', '')
    el.replace_with(soup.new_string(f'\n\n$$\n{math_content}\n$$\n\n'))

# Replace math-inline with $...$
for el in mc.find_all(attrs={'class': lambda c: c and 'math-inline' in str(c)}):
    math_content = el.get('data-math', '')
    el.replace_with(soup.new_string(f'${math_content}$'))

# Remove UI noise
for el in mc.find_all(['button', 'mat-icon', 'sources-carousel', 'sources-carousel-inline', 'source-footnote', 'gem-icon', 'gem-button']):
    el.decompose()

# Clean code blocks: inside <pre><code>, keep the raw text
for pre in mc.find_all('pre'):
    code = pre.find('code')
    if code:
        raw_code = code.get_text()
        code.clear()
        code.string = raw_code

html_str = str(mc)
markdown_text = md(html_str, heading_style='ATX', bullets='-')

# Clean up formatting artifacts:
markdown_text = re.sub(r'\n(?:JSON|json)\s*\n+```', '\n```json', markdown_text)

# Unescape underscores in LaTeX formulas
def unescape_math(match):
    return match.group(0).replace(r'\_', '_')

markdown_text = re.sub(r'\$\$.*?\$\$', unescape_math, markdown_text, flags=re.DOTALL)
markdown_text = re.sub(r'\$.*?\$', unescape_math, markdown_text)

# Clean up extra blank lines
markdown_text = re.sub(r'\n{3,}', '\n\n', markdown_text).strip()

output_path = '/home/hari/code/python/define/multilingual_outbound_campaign_systems.md'
with open(output_path, 'w', encoding='utf-8') as f:
    f.write(markdown_text + '\n')

print(f'Successfully updated {output_path}')
print(f'Final file size: {len(markdown_text)} chars, {len(markdown_text.splitlines())} lines')
