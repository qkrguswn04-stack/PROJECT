import os,json
from collections import Counter

base = "/home/ubuntu/workspace/dataset/dataset001/049.난소암 데이터/3.개방데이터/1.데이터"
benign_meta = os.path.join(base, "Other/메타데이터/양성종양/EMR")

postop_when_none = Counter()
postop_all = Counter()

for f in os.listdir(benign_meta):
	with open(os.path.join(benign_meta, f), "r", encoding="utf-8") as fp:
		m=json.load(fp)
		postop_all[m.get("POSTOP_PATH")] += 1
		if m.get("FND") is None :
			postop_when_none[m.get("POSTOP_PATH")] += 1

print("전체 POSTOP_PATH 분포:", dict(postop_all))
print("FND None일 때 POSTOP_PATH 분포:", dict(postop_when_none))

