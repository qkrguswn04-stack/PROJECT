import pandas as pd
from preprocessor import OvaPreprocessor
from trainer import OvaTrainer

# 1. 데이터 로드
df = pd.read_csv('여기에_파일명.csv')
print(f"[데이터] {df.shape[0]}명, {df.shape[1]}개 컬럼")

# 2. 전처리
prep = OvaPreprocessor()
df_processed = prep.fit_transform(df)

# 3. 데이터 분할
trainer = OvaTrainer()
X_train, X_test, y_train, y_test = trainer.prepare_data(df_processed)

# 4. ROMA baseline
roma_auc = trainer.roma_baseline(df_processed)

# 5. 모델 학습
trainer.train_all(X_train, y_train)

# 6. 평가
final_auc = trainer.evaluate(X_test, y_test, roma_baseline_auc=roma_auc)

# 7. SHAP
trainer.explain_shap(X_train)

# 8. 저장
trainer.save('best_model.pkl')

print(f"\n목표 AUC 0.85 → {'✅ 달성' if final_auc >= 0.85 else '❌ 미달성'}")
print(f"ROMA 초과     → {'✅' if final_auc > roma_auc else '❌'}")
