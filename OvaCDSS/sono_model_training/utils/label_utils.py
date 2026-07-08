MALIGNANT_SUBTYPE_MAP = {
"Serous carcinoma": "serous",
"Endometrioid carcinoma":"endometrioid",
"Mucinous carcinoma":"mucinous",
"Clear cell carcinoma":"clear_cell",
"Etc":"etc",
}

BENIGN_SUBTYPE_MAP ={
"Mature teratoma": "teratoma", 
"Endometrioid tumor": "endometrioid",
"Mucinous tumor": "mucinous",
"Serous tumor": "serous",
"Etc": "etc",
}

def stage_to_group(stage_str):
    """FIGO Stage ->  1,2기 vs 3,4기 (악성에만 적용, None이면 None)"""
    if stage_str is None:
        return None
    if stage_str.startswith("IV") or stage_str.startswith("III"):
        return "3,4기"
    elif stage_str.startswith("II") or stage_str.startswith("I"):
        return "1,2기"

def map_malignant_type(fnd_value):
    """ 악성 종양 세부 조직형 매핑, 매핑 안되면 NOne (subtype 학습 제외)"""
    return MALIGNANT_SUBTYPE_MAP.get(fnd_value)

def map_benign_type(fnd_value):
    """양성 종양 세부 조직형 매핑. 매핑 안되면None (subtype 학습제외)"""
    return BENIGN_SUBTYPE_MAP.get(fnd_value)
