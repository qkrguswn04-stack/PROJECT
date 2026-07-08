import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler, LabelEncoder
from config import FEATURE_CONFIG


class OvaPreprocessor:
    def __init__(self):
        self.scaler = StandardScaler()
        self.fitted = False

    def _encode_categoricals(self, df):
        cat_cols = df.select_dtypes(include=['object', 'category']).columns
        for col in cat_cols:
            le = LabelEncoder()
            df[col] = le.fit_transform(df[col].astype(str))
        return df

    def _add_roma_features(self, df):
        if 'he4' in df.columns and 'ca125' in df.columns:
            df['ln_he4']   = np.log(df['he4'].clip(lower=0.1))
            df['ln_ca125'] = np.log(df['ca125'].clip(lower=0.1))

            pre_mask  = df['menopause'] == 0
            post_mask = df['menopause'] == 1

            df.loc[pre_mask,  'roma_pi'] = -12.0 + 2.38   * df.loc[pre_mask,  'ln_he4'] + 0.0626 * df.loc[pre_mask,  'ln_ca125']
            df.loc[post_mask, 'roma_pi'] = -8.09 + 1.04   * df.loc[post_mask, 'ln_he4'] + 0.732  * df.loc[post_mask, 'ln_ca125']

            df['roma_score_calc'] = np.exp(df['roma_pi']) / (1 + np.exp(df['roma_pi'])) * 100
        return df
    
    def fit_transform(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        target = df.pop(FEATURE_CONFIG['target'])

        df = self._encode_categoricals(df)
        df = self._add_roma_features(df)

        num_cols = df.select_dtypes(include='number').columns
        df[num_cols] = self.scaler.fit_transform(df[num_cols])

        self.fitted = True
        df[FEATURE_CONFIG['target']] = target.values
        
        return df

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        assert self.fitted, "fit_transform 먼저 실행하세요"
        df = df.copy()

        df = self._encode_categoricals(df)
        df = self._add_roma_features(df)

        num_cols = df.select_dtypes(include='number').columns
        df[num_cols] = self.scaler.transform(df[num_cols])
        return df