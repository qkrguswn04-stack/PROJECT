from PIL import Image
import os, random

base = "/home/ubuntu/workspace/dataset/dataset001/049.난소암 데이터/3.개방데이터/1.데이터"
img_dir = os.path.join(base, "Training/01.원천데이터/암/초음파")

files = random.sample(os.listdir(img_dir), 100)
sizes = set(Image.open(os.path.join(img_dir, f)).size for f in files)
print(sizes)
#for f in files:
#	img = Image.open(os.path.join(img_dir, f))
#	print(f, "->", img.size)


#sizes = set()
#for f in os.listdir(img_dir):
#	img = Image.open(os.path.join(img_dir, f))
#	sizes.add(img.size)

#print('크기종류:', sizes)
#print('총 종류 수:', len(sizes))


#import struct, os
#
#sizes = set()
#for f in os.listdir(img_dir):
#	with open(os.path.join(img_dir, f), 'rb') as fp:
#		fp.read(16)
#		w = struct.unpack('>I', fp.read(4))[0]
#		h = struct.unpack('>I', fp.read(4))[0]
#		sizes.add((w, h))

#print('크기 종류:', sizes)
