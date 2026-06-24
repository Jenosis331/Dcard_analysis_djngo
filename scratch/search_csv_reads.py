import os

root_dir = r"c:\Users\Chen\Desktop\proj\website-news-analysis_14 _docker"
results = []
for root, dirs, files in os.walk(root_dir):
    if any(p in root for p in ['.git', '.claude', '__pycache__', '.gemini', 'scratch']):
        continue
    for file in files:
        if file.endswith('.py'):
            filepath = os.path.join(root, file)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    for idx, line in enumerate(lines):
                        if 'read_csv' in line:
                            results.append((filepath, idx + 1, line.strip()))
            except Exception as e:
                pass

print(f"Found {len(results)} occurrences of read_csv:")
for r in results:
    print(f"File: {r[0]} | Line {r[1]}: {r[2]}")
