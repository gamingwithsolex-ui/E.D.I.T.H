import os

file_path = 'c:/Users/Amal_/Downloads/project-- edith/edith/interfaces/web/templates/index.html'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix corrupted characters
content = content.replace('A-</button>', 'x</button>')
content = content.replace('o-', 'x')
content = content.replace('SYS ?', 'SYS &gt;')
content = content.replace('LAT ?" A LON ?"', 'LAT --- LON ---')
content = content.replace('TACTICAL GRID A INITIALIZING', 'TACTICAL GRID INITIALIZING')
content = content.replace('PERSONAL AI  SYSTEM ONLINE', 'PERSONAL AI - SYSTEM ONLINE')
content = content.replace('E.D.I.T.H. ?" AI System', 'E.D.I.T.H. - AI System')

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Fixed corrupted characters successfully.")
