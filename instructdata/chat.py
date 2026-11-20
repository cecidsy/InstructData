"""将数据问题转换为有限的分析操作，并在当前数据表上执行。"""

import json
import os
from dataclasses import dataclass, field
from io import BytesIO
from itertools import chain
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

import pandas as pd
from openpyxl import Workbook

from .analysis import column_summary, group_summary

OPERATIONS = {"reply", "preview", "summary", "count", "sum", "mean", "max", "min",
              "filter", "sort", "deduplicate", "drop_missing", "fill_missing"}
AGGREGATIONS = {"count": "计数", "sum": "求和", "mean": "平均值", "max": "最大值", "min": "最小值"}
TRANSFORMS = {"filter", "sort", "deduplicate", "drop_missing", "fill_missing"}


@dataclass
class ChatResult:
    message: str
    table: pd.DataFrame | None = None
    chart: str | None = None
    download: bytes | None = None
    preview: pd.DataFrame | None = None


@dataclass(frozen=True)
class ModelConfig:
    url: str
    name: str
    api_key: str = field(default="", repr=False)

    def __post_init__(self):
        endpoint = urlsplit(self.url)
        if endpoint.scheme not in ("http", "https") or not endpoint.hostname:
            raise ValueError("请输入完整的 HTTP 或 HTTPS 对话接口地址。")
        if not self.name:
            raise ValueError("请输入模型名称。")


def environment_model():
    endpoint = os.getenv("INSTRUCTDATA_MODEL_URL", "").strip()
    name = os.getenv("INSTRUCTDATA_MODEL", "").strip()
    if endpoint and name:
        return ModelConfig(endpoint, name, os.getenv("INSTRUCTDATA_MODEL_API_KEY", ""))


def model_plan(question, data, previous=None, *, config, previous_question=None, excel=False):
    """由模型解释问题，本地引擎执行返回的有限操作。"""
    schema = {} if data is None else {column: str(dtype) for column, dtype in data.dtypes.items()}
    instructions = (
        "你是 InstructData ChatBI，始终用自然中文理解用户，可处理口语、同义词、上下文追问。"
        "只返回一个 JSON 对象。询问功能、问候或暂未选数据时可返回 "
        '{"operation":"reply","message":"简洁、具体的中文答复"}。'
        "有表时，‘这张表有什么数据’、‘里面都是什么’请选择 summary，可设置 preview=true 附本地样例；"
        "如用户明确要看前几条，使用 preview 操作和 limit。"
        "能力包括单表问数、柱状图/折线图/散点图、Excel 筛选排序去重删空行填补缺失值和导出。"
        f"操作取 {', '.join(sorted(OPERATIONS))}。"
        "field 是数值列或处理列，group 是分组列，chart 取 bar/line/scatter 或 null，"
        "limit 是前几组或前几行，descending 是排序方向，value 是填充值。"
        "filter 可选，含 field、comparison（eq/ne/gt/ge/lt/le/contains）和标量 value。"
        "count 统计记录条数。只使用给定字段真实列名，优先将用户术语对应到含义明确的列。"
        "没有对应字段时指出当前有哪些相关字段并询问；绝不猜测字段或统计结果。"
        "追问可复用上一条执行成功的计划和上一条用户问题。"
        '仍需确认时返回 {"clarify":"具体说明需要确认的信息"}。'
    )
    request = Request(config.url, method="POST", data=json.dumps({
        "model": config.name,
        "messages": [
            {"role": "system", "content": instructions},
            {"role": "user", "content": json.dumps({
                "字段": schema, "已读取行数": len(data) if data is not None else None,
                "可导出Excel": excel, "问题": question,
                "上一条问题": previous_question, "上一条计划": previous,
            }, ensure_ascii=False)},
        ],
    }, ensure_ascii=False).encode("utf-8"), headers={"Content-Type": "application/json"})
    if config.api_key:
        request.add_header("Authorization", f"Bearer {config.api_key}")
    try:
        with urlopen(request, timeout=35) as response:
            content = json.loads(response.read(1024 * 1024))["choices"][0]["message"]["content"]
        content = content.strip()
        if content.startswith("```") and content.endswith("```") and "\n" in content:
            content = content.split("\n", 1)[1][:-3]
        plan = json.loads(content)
    except HTTPError as error:
        if error.code in (401, 403):
            raise ValueError("模型服务拒绝认证，请检查 API 密钥与模型访问权限。") from error
        if error.code == 404:
            path = urlsplit(config.url).path.rstrip("/")
            if path.endswith("/v1"):
                raise ValueError("模型服务返回 HTTP 404。请填写完整对话接口，例如在 /v1 后加上 /chat/completions。") from error
            raise ValueError("模型服务返回 HTTP 404。请核对完整接口地址和服务方提供的模型 ID（含大小写），并确认当前业务空间有访问权限。") from error
        raise ValueError(f"模型服务返回 HTTP {error.code}，请检查接口地址、模型名称或服务状态。") from error
    except (URLError, TimeoutError) as error:
        raise ValueError("无法连接模型服务或请求超时，请检查接口地址和网络。") from error
    except (AttributeError, KeyError, ValueError, TypeError, IndexError) as error:
        raise ValueError("模型服务未返回有效的分析计划。") from error
    if not isinstance(plan, dict):
        raise ValueError("模型未返回有效的分析计划。")
    if isinstance(plan.get("clarify"), str):
        return {"operation": "reply", "message": plan["clarify"]}
    return plan


def field_value(series, value):
    if value is None or not isinstance(value, (str, int, float, bool)):
        raise ValueError("请提供一个数字、日期或文本值。")
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(value)
    if pd.api.types.is_datetime64_any_dtype(series):
        return pd.to_datetime(value)
    return str(value)


def apply_filter(data, condition):
    if not isinstance(condition, dict) or condition.get("field") not in data.columns:
        raise ValueError("筛选条件需要有效的字段。")
    series = data[condition["field"]]
    comparison = condition.get("comparison")
    value = condition.get("value")
    if comparison == "contains" and isinstance(value, str):
        matches = series.astype("string").str.contains(value, regex=False, na=False)
    elif comparison in ("eq", "ne", "gt", "ge", "lt", "le"):
        matches = getattr(series, comparison)(field_value(series, value)) & series.notna()
    else:
        raise ValueError("暂不支持此筛选比较方式。")
    return data.loc[matches]


def workbook_bytes(data):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "处理结果"
    for row in chain([data.columns], data.itertuples(index=False, name=None)):
        sheet.append([None if pd.isna(value) else value for value in row])
        for cell in sheet[sheet.max_row]:
            if cell.data_type in {"f", "e"}:
                cell.data_type = "s"
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def execute(plan, data, excel=False):
    operation, field, group, chart = (plan.get(key) for key in ("operation", "field", "group", "chart"))
    if not isinstance(operation, str) or operation not in OPERATIONS:
        raise ValueError("暂不支持该操作。")
    if operation == "reply":
        message = plan.get("message")
        if not isinstance(message, str) or not message.strip():
            raise ValueError("模型未返回答复内容。")
        return ChatResult(message.strip()[:2000])
    if data is None:
        raise ValueError("请先上传 Excel 或连接数据库并选择一张表。")
    if any(name is not None and (not isinstance(name, str) or name not in data.columns) for name in (field, group)):
        raise ValueError("分析计划包含当前数据中不存在的字段。")
    if chart not in (None, "bar", "line", "scatter"):
        raise ValueError("暂不支持该图表类型。")
    limit = plan.get("limit")
    if limit is not None and (type(limit) is not int or not 1 <= limit <= 1000):
        raise ValueError("结果数量须为 1 到 1000 的整数。")
    if plan.get("filter") is not None:
        data = apply_filter(data, plan["filter"])
    if operation == "summary":
        preview = data.head(5) if plan.get("preview") is True else None
        return ChatResult(f"当前范围有 {len(data):,} 行、{len(data.columns)} 列。",
                          column_summary(data).reset_index(), preview=preview)
    if operation == "preview":
        preview = data.head(min(limit or 10, 100))
        return ChatResult(f"显示当前范围内的前 {len(preview):,} 行。", preview)
    if operation in AGGREGATIONS:
        label = AGGREGATIONS[operation]
        if operation != "count" and (field is None or field not in data.select_dtypes(include="number").columns):
            raise ValueError(f"请指定用于{label}的数值字段。")
        if group is None:
            if chart:
                raise ValueError("绘制图表需要分组字段，例如“按地区汇总金额，画柱状图”。")
            value = len(data) if operation == "count" else (
                data[field].sum(min_count=1) if operation == "sum" else getattr(data[field], operation)())
            result = "无有效数据" if pd.isna(value) else f"{value:,g}" if isinstance(value, float) else str(value)
            return ChatResult(f"{field or '记录'} · {label}：{result}。统计范围为 {len(data):,} 行。")
        if operation in ("count", "sum", "mean"):
            totals = group_summary(data, group, label, field)
        else:
            values = data.groupby(group, dropna=False, observed=True)[field]
            totals = getattr(values, operation)().sort_values(ascending=False)
        if chart == "line" and limit is None:
            totals = totals.sort_index()
        output = totals.head(limit) if limit else totals
        metrics = f"{field} · {label}" if field else label
        if metrics == group:
            metrics = f"{label}结果"
        table = output.rename(metrics).rename_axis(group).reset_index()
        if table.empty:
            return ChatResult("当前筛选范围内没有可分组的数据。", table)
        return ChatResult(f"按「{group}」计算{metrics}，基于 {len(data):,} 行，返回 {len(table):,} 组。",
                          table, chart)
    if operation == "filter" and plan.get("filter") is None:
        raise ValueError("请给出筛选条件。")
    if operation in ("sort", "fill_missing") and field is None:
        raise ValueError("请指定要处理的字段。")
    if operation == "sort":
        data = data.sort_values(field, ascending=not plan.get("descending", True), kind="stable")
    elif operation == "deduplicate":
        data = data.drop_duplicates(subset=field)
    elif operation == "drop_missing":
        data = data.dropna(subset=[field]) if field else data.dropna(how="all")
    elif operation == "fill_missing":
        data = data.copy()
        data[field] = data[field].fillna(field_value(data[field], plan.get("value")))
    if limit:
        data = data.head(limit)
    if chart and (not group or not field or group == field or field not in data.select_dtypes(include="number")):
        raise ValueError("请指定图表的横轴字段和数值字段。")
    chart_table = data[[group, field]] if chart else data
    download = workbook_bytes(data) if excel and operation in TRANSFORMS else None
    return ChatResult(f"已完成表格处理，结果包含 {len(data):,} 行、{len(data.columns)} 列。",
                      chart_table, chart, download)
