
import sys
sys.path.insert(0, '/home/ubuntu/project/AI-HUB환경/sonography')
from label_utils import stage_to_group, map_malignant_type
print(stage_to_group('IIIC'))
print(stage_to_group('IA'))
print(map_malignant_type('Serous carcinoma'))
