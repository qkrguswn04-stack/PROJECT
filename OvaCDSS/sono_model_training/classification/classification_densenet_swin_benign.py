import os
import random
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms
from torchvision.transforms import InterpolationMode
import timm
from PIL import Image
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, roc_auc_score, confusion_matrix
import json
import pandas as pd

# ====================================
# Swin Transformer
# ====================================

SEED = 9

def set_seed(seed=42):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed(seed)
    torch.backends.cudnn.deterministic = True
    
set_seed(SEED)


# ==========================================
# 1. 경로 설정 
# ==========================================
LABELS_CSV = "/home/ubuntu/project/AI-HUB_preprocess/labels.csv"
TRAIN_IMG_DIR = "/home/ubuntu/project/AI-HUB_preprocess/yolo_dataset/train/images"
VAL_IMG_DIR = "/home/ubuntu/project/AI-HUB_preprocess/yolo_dataset/val/images"
SAVE_BASE = "/home/ubuntu/project/AI-HUB_preprocess/runs/classification_densenet_swin_3class_seed9_benign"
os.makedirs(SAVE_BASE, exist_ok=True)

CLASS_NAMES = ["teratoma", "endometrioid", "mucinous", "serous", "etc"]



# ====================================
# 2. 3 class mapping
# ====================================
SUBTYPE_MAP = {
    'teratoma' : 0,
    'endometrioid' : 1,
    'mucinous' : 2,
    'serous' : 3,
    'etc' : 4
}

def get_label(subtype):
    return SUBTYPE_MAP.get(subtype, 4)

# ====================================
# 3. data set class
# ====================================

class AIHUBDataset(Dataset):
    def __init__(self, samples, transform=None):
        self.samples = samples
        self.transform = transform
        
    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        img_path, label = self.samples[idx]
        image = Image.open(img_path).convert('RGB')
        if self.transform:
            image = self.transform(image)
        return image, label
        

# ====================================
# 4. data 증강 
# ==================================== 

train_transform = transforms.Compose([
    transforms.Resize((224, 224), interpolation=InterpolationMode.NEAREST),
    transforms.RandomHorizontalFlip(p=0.5),
    transforms.RandomVerticalFlip(p=0.3),
    transforms.RandomRotation(degrees=10),
    transforms.ColorJitter(brightness=0.2, contrast=0.2),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406],
                        std=[0.229, 0.224, 0.225])
])

val_transform = transforms.Compose([
    transforms.Resize((224, 224), interpolation=InterpolationMode.NEAREST),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406],
                        std=[0.229, 0.224, 0.225])
])


# ====================================
# 5. data load 및 분리  
# ====================================       
print("데이터 로드 중...")
df = pd.read_csv(LABELS_CSV)
df['stage_group'] = df['stage_group'].str.replace("'","").str.strip()

# Benign Only
df = df[df['malignancy'] == 'benign'].reset_index(drop=True)
df = df.dropna(subset=['subtype']).reset_index(drop=True)
df['label'] = df['subtype'].apply(lambda x: get_label(x))

print(f"양성 subtype 분포:")
print(df['label'].value_counts())

train_full = df

train_df, val_df = train_test_split(
    train_full, test_size = 0.3, random_state=SEED, stratify=train_full['label']
)

n_train = len(train_df[train_df['label'].values == 4])
n_val = len(val_df[val_df['label'].values == 4])

n_early = n_train
print(f"전체 - teratoma {(train_full['label'].values==0).sum()}")
print(f"endometrioid {(train_full['label'].values==1).sum()}")
print(f"mucinous {(train_full['label'].values==2).sum()}")
print(f"serous {(train_full['label'].values==3).sum()}")
print(f"etc {(train_full['label'].values==4).sum()}")

def balance_samples(df, n, seed):
    return pd.concat([
        df[df['label'].values == i].sample(n=n, random_state=seed)
        for i in range(5)
    ])

train_balanced = balance_samples(train_df, n_train, SEED)
val_balanced = balance_samples(val_df, n_val, SEED)


def build_samples(balanced_df, img_dir):
    samples = []
    for _, row in balanced_df.iterrows():
        label = row['label']
        fname = os.path.basename(row['image_path'])
        img_path = os.path.join(img_dir, fname)
        if os.path.exists(img_path):
            samples.append((img_path, row['label']))
    return samples
    
train_samples = build_samples(train_balanced, TRAIN_IMG_DIR)
val_samples = build_samples(val_balanced, VAL_IMG_DIR)


print(f"Train: {len(train_samples)}장 (1:1:1:1:1 비율, seed = {SEED})")
for i, name in enumerate(CLASS_NAMES):
    print(f"    {name}: {sum(1 for _, l in train_samples if l == i )}장")
    
print(f"Val: {len(train_samples)}장 (1:1:1:1:1 비율, seed = {SEED})")
for i, name in enumerate(CLASS_NAMES):
    print(f"    {name}: {sum(1 for _, l in val_samples if l == i )}장") 
    
train_dataset = AIHUBDataset(train_samples, train_transform)
val_dataset = AIHUBDataset(val_samples, val_transform)

train_loader = DataLoader(train_dataset, batch_size=32, shuffle=True, num_workers=4)
val_loader = DataLoader(val_dataset, batch_size=32, shuffle=False, num_workers=4)


# ====================================
# 6. 클래스 불균형 대응(class_weights)  
# ====================================

label_list = [l for _, l in train_samples]
class_counts = [label_list.count(i) for i in range(5)]
total = sum(class_counts)
class_weights = torch.FloatTensor([total/c for c in class_counts])
print(f"\n Class Weights: {[f' {w:.2f}' for w in class_weights]}")


# ====================================
# 7. Swin Transformer model 
# ====================================
import torch
torch.hub.set_dir('/home/ubuntu/.cache/torch/hub')

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print(f"\n Divice: {device}")

class DenseNetSwinEarlyFusion(nn.Module):
    def __init__(self, num_classes=5):
        super().__init__()
        
        #DenseNet121 (CNN branch)
        self.densenet = timm.create_model(
            'densenet121',
            pretrained=False,
            num_classes=0,
            global_pool='avg'
        )
        dense_dim = self.densenet.num_features
        
        state_dict = torch.load('/home/ubuntu/.cache/torch/hub/checkpoints/densenet121-a639ec97.pth')
        new_sd = {}
        for k, v in state_dict.items():
            new_k = k
            if not new_k.startswith('features.'):
                new_k = 'featrues.' + new_k
            
            new_k = new_k.replace('.norm.1.', '.norm1.').replace('.norm.2.', '.norm2.').replace('.conv.1.', '.conv1.').replace('.conv.2.', '.conv2.')
            new_sd[new_k] = v
        
        matched = self.densenet.load_state_dict(new_sd, strict=False)
    
        total_timm_keys = len(self.densenet.state_dict().keys())
        missing_keys_count = len(matched.missing_keys)
        loaded_keys_count = total_timm_keys - missing_keys_count
    
        print(f"정확히 로드된 키 개수:{loaded_keys_count}/전체 키 개수:{total_timm_keys}")
        if missing_keys_count > 0:
            print(f"로드되지않은 키 샘플 상위 5개): {list(matched.missing_keys)[:5]}")
        
        print('='*50)
        
        
        #Swin Transformer (Transformer branch)
        self.swin = timm.create_model(
            'swin_tiny_patch4_window7_224', 
            pretrained=True, 
            num_classes=0, 
            global_pool='avg'
        )
        swin_dim = self.swin.num_features
        
        #Early-fusion:concat
        fused_dim = dense_dim + swin_dim
        
        #Classification Head
        self.classifier = nn.Sequential(
            nn.LayerNorm(fused_dim),
            nn.Dropout(0.3),
            nn.Linear(fused_dim, 512),
            nn.GELU(),
            nn.Dropout(0.3),
            nn.Linear(512, num_classes)
        )
    
        # DenseNet 초반 고정
        for name, param in self.densenet.named_parameters():
            if 'features.denseblock1' in name or 'features.conv0' in name:
                param.requires_grad = False
            
        # Swin 초반 고정
        for name, param in self.swin.named_parameters():
            if 'patch_embed' in name or 'layers.0' in name:
                param.requires_grad = False
                
    def forward(self, x):
        dense_features = self.densenet(x)
        swin_features = self.swin(x)
        fused = torch.cat([dense_features, swin_features], dim=1)
        out = self.classifier(fused)
        return out
        
print ("DenseNet + Swin Transformer Early-fusion 모델 로드 중...")
model = DenseNetSwinEarlyFusion(num_classes=5).to(device)
print("모델 로드 완료!")
   

criterion = nn.CrossEntropyLoss(weight=class_weights.to(device))
optimizer = optim.AdamW(
    filter(lambda p: p.requires_grad, model.parameters()),
    lr=0.0001, weight_decay=0.05
)
scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=5, factor=0.5)

# ====================================
# 8. 학습 함수  
# ====================================

def train_epoch(model, loader, criterion, optimizer):
    model.train()
    total_loss = 0
    correct = 0
    total = 0
    
    for images, labels in loader:
        images, labels = images.to(device), labels.to(device)
        optimizer.zero_grad()
        outputs = model(images)
        loss = criterion(outputs, labels)
        loss.backward()
        optimizer.step()
        
        total_loss += loss.item()
        _, predicted = outputs.max(1)
        correct += predicted.eq(labels).sum().item()
        total += labels.size(0)
        
    return total_loss / len(loader), correct / total
    
    
# ====================================
# 9. 평가  함수  
# ====================================

def evaluate(model, loader, criterion):
    model.eval()
    total_loss = 0
    all_preds = []
    all_labels = []
    all_probs = []
    
    with torch.no_grad():
        for images, labels in loader:
            images, labels = images.to(device), labels.to(device)
            outputs = model(images)
            loss = criterion(outputs, labels)
            total_loss += loss.item()

            probs = torch.softmax(outputs, dim=1)
            _, predicted = outputs.max(1)

            all_preds.extend(predicted.cpu().numpy())
            all_labels.extend(labels.cpu().numpy())
            all_probs.extend(probs.cpu().numpy())
            
    report = classification_report(all_labels, all_preds,
                                  target_names=CLASS_NAMES,
                                  output_dict=True,
                                  zero_division=0)
    auc = roc_auc_score(all_labels, all_probs, multi_class='ovr', average='macro')
    cm = confusion_matrix(all_labels, all_preds)
    
    return {
        'loss': total_loss / len(loader),
        'accuracy': report['accuracy'],
        'f1_teratoma' : report['teratoma']['f1-score'],
        'f1_endometrioid' : report['endometrioid']['f1-score'],
        'f1_mucinous' : report['mucinous']['f1-score'],
        'f1_serous' : report['serous']['f1-score'],
        'f1_etc' : report['etc']['f1-score'],
        'auc': auc,
        'confusion_matrix': cm.tolist()
    }


# ====================================
# 10. 학습 실행   
# ====================================

print(f"\nDenseNet + Swin Transformer 5클래스 학습 시작 (seed={SEED})...")
print("=" * 50)

best_auc = 0
best_sensitivity = 0
epochs = 70
results = []

for epoch in range(epochs):
    train_loss, train_acc = train_epoch(model, train_loader, criterion, optimizer)
    val_metrics = evaluate(model, val_loader, criterion)
    scheduler.step(val_metrics['loss'])
    
    results.append({
        'epoch': epoch + 1,
        'train_loss': train_loss,
        'train_acc': train_acc,
        **val_metrics
    })
    
    if val_metrics['auc'] > best_auc:
        best_auc = val_metrics['auc']
        torch.save(model.state_dict(), os.path.join(SAVE_BASE, 'best_auc.pth'))
        
        
    if (epoch + 1) % 5 == 0:
        print(f"Epoch [{epoch+1}/{epochs}]")
        print(f"  Train Loss:{train_loss:.4f}, Train Acc:{train_acc:.4f}")
        print(f"  AUC:{val_metrics['auc']:.4f}")
        print(f"  Accuracy:{val_metrics['accuracy']:.4f}")
        
# ====================================
# 11. 최종 결과   
# ====================================        

best_result = max(results, key=lambda x:x['auc'])
print("\n" + "=" * 50)
print(f"DenseNet + Swin benign subtype 학습 완료! (seed={SEED})")
print(f"/n Best 결과 (Epoch {best_result['epoch']})")
print(f"AUC:                {best_result['auc']:.4f}")
print(f"Accuracy:           {best_result['accuracy']:.4f}")
for name in CLASS_NAMES:
    print(f"F1 {name} : {best_result[f'f1_{name}']:.4f}")
print(f"\n 저장경로:{SAVE_BASE}")


with open(os.path.join(SAVE_BASE, 'all_results.json'), 'w') as f:
    json.dump(results, f, indent=2)

























