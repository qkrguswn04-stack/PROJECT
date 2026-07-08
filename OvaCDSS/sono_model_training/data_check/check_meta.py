import os, json
from collections import Counter

base = "/home/ubuntu/workspace/dataset/dataset001/049.난소암 데이터/3.개방데이터/1.데이터"
benign_meta = os.path.join(base, "Other/메타데이터/양성종양/EMR")

files = os.listdir(benign_meta)
print("총 파일 수:", len(files))


fnd_values = Counter()
sample = None

for i, f in enumerate(files):
	if i % 200 == 0:
		print("진행:", i, "/", len(files))
	with open(os.path.join(benign_meta, f), "r", encoding="utf-8") as fp:
		m = json.load(fp)
		fnd_values[m.get("FND")] += 1
		if sample is None:
			sample = m

print("===양성종양 FND 분포 ===")
for val, cnt in fnd_values.most_common():
	print(f"{val!r}: {cnt}")

print("\n=== sample ===")
print(json.dumps(sample, indent=2, ensure_ascii=False))
