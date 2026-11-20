"""对 Excel 和数据库共用的 DataFrame 做统计。"""

import pandas as pd

GROUP_OPERATIONS = ("计数", "求和", "平均值")


def column_summary(data):
    return pd.DataFrame({
        "数据类型": data.dtypes.astype(str),
        "缺失值": data.isna().sum(),
        "非空不同值": data.nunique(),
    }).rename_axis("字段")


def group_summary(data, group_column, operation, value_column=None):
    if operation not in GROUP_OPERATIONS:
        raise ValueError(f"不支持的统计方式：{operation}")
    groups = data.groupby(group_column, dropna=False, observed=True, sort=False)
    if operation == "计数":
        result = groups.size()
    elif operation == "求和":
        result = groups[value_column].sum(min_count=1)
    else:
        result = groups[value_column].mean()
    return result.sort_values(ascending=False).rename(operation)
