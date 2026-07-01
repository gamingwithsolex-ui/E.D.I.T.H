import os

file_path = 'c:/Users/Amal_/Downloads/project-- edith/edith/interfaces/web/templates/index.html'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix the classes that got mangled by replacing 'o-' with 'x'
content = content.replace('logx', 'logo-')
content = content.replace('infx', 'info-')
content = content.replace('videx', 'video-')
content = content.replace('radix', 'radio-')
content = content.replace('autx', 'auto-')
content = content.replace('txdx', 'todo-')
content = content.replace('txd', 'tod')  # in case
content = content.replace('xverlay', 'overlay')
content = content.replace('bxottom', 'bottom')
content = content.replace('mxc', 'moc')

# The REPLACEMENT characters! The file has ''. We can use regex to replace it!
import re
content = re.sub(r'PERSONAL AI [^\s]* SYSTEM ONLINE', 'PERSONAL AI - SYSTEM ONLINE', content)
content = re.sub(r'SYS [^\s]*', 'SYS > ', content)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Fixed classes and unicode characters successfully.")
