FEATURE_CONFIG = {
    'must': ['ca125', 'he4', 'menopause', 'age'],
    'explore': ['cea', 'ldh', 'ca19_9', 'afp', 'bmi', 'alb'],
    'target': 'malignant',
}

MODEL_CONFIG = {
    'test_size': 0.2,
    'random_state': 42,
    'cv_folds': 5,
    'target_auc': 0.85,
}

ROMA_THRESHOLDS = {
    'pre': 11.4,
    'post': 29.9,
}

DB_SHAPE = {
    'db_url': 'postgresql+psycopg://team2:5inyoung@/mimic',    
    'schema': 'mimic_ova',
    'table': 'patient',
}