"""发票类型分类模块"""

# 分类规则：先匹配先得
CATEGORY_RULES: list[tuple[str, list[str]]] = [
    ("住宿发票", ["住宿", "客房", "酒店", "宾馆", "民宿"]),
    ("餐饮发票", ["餐饮", "餐费", "食品", "餐厅", "饭店", "外卖"]),
    ("飞机火车发票", ["航空", "机票", "铁路", "火车", "高铁", "动车", "航班"]),
    ("打车发票", ["网约车", "出租", "滴滴", "曹操", "T3", "运输"]),
]
DEFAULT_CATEGORY = "其他发票"


def classify_invoice(service_name: str, raw_text: str = "") -> str:
    """
    根据服务名称（及原始文本兜底）分类发票。
    返回类型字符串，如 '住宿发票'。
    """
    search_text = f"{service_name}\n{raw_text}"
    for category, keywords in CATEGORY_RULES:
        for kw in keywords:
            if kw in search_text:
                return category
    return DEFAULT_CATEGORY
