import os

file_path = 'c:/Users/Amal_/Downloads/project-- edith/edith/interfaces/web/templates/index.html'
with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

out_lines = []
for line in lines:
    if line.endswith('\n'):
        line = line[:-1]
    
    # PowerShell -replace '', '-' adds '-' at start, between chars, and at end.
    # We want chars at index 1, 3, 5...
    if len(line) > 0 and line[0] == '-':
        recovered = line[1::2]
        out_lines.append(recovered + '\n')
    else:
        out_lines.append(line + '\n')

with open(file_path, 'w', encoding='utf-8') as f:
    f.writelines(out_lines)
print("Recovered index.html successfully.")
