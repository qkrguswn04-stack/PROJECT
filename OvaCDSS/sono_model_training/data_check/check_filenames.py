import os

base = "/home/ubuntu/workspace/dataset/dataset001/049.난소암 데이터/3.개방데이터/1.데이터"

img_dir = os.path.join(base, "Training/01.원천데이터/암/초음파")
meta_dir = os.path.join(base, "Other/메타데이터/암/EMR")

print("===img 파일명sample")
print(os.listdir(img_dir)[:5])

print("\n === 메타데이터 파일명 샘플 ===")
print(os.listdir(meta_dir)[:5])

