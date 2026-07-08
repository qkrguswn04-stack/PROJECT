import os, json

base = "/home/ubuntu/workspace/dataset/dataset001/049.난소암 데이터/3.개방데이터/1.데이터"
label_dir = os.path.join(base, "Training/02.라벨링데이터/암/초음파")

files = os.listdir(label_dir)
print("파일 수:", len(files))
print("샘플 파일 명:", files[:3])

with open(os.path.join(label_dir, files[0]), "r", encoding="utf-8") as f:
	sample = json.load(f)

print(json.dumps(sample, indent=2, ensure_ascii=False))


