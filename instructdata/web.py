"""ChatBI 主界面与数据源配置。"""

from hashlib import sha256

import pandas as pd
import streamlit as st
from sqlalchemy import URL
from sqlalchemy.exc import SQLAlchemyError

from .analysis import GROUP_OPERATIONS, column_summary, group_summary
from .chat_view import show_chat
from .sources import ROW_LIMIT, list_tables, open_workbook, read_sheet, read_table, sqlite_url


def excel_source():
    upload = st.file_uploader("上传 Excel 文件", type=["xlsx", "xls"])
    if upload is None:
        return None
    try:
        with open_workbook(upload) as workbook:
            sheet = st.selectbox("工作表", workbook.sheet_names)
            if sheet is not None:
                data = read_sheet(workbook, sheet)
                return (sha256(upload.getbuffer()).hexdigest(), sheet), sheet, data
    except Exception:
        st.error("无法读取工作簿。请检查文件是否损坏、加密或格式不匹配。")
    return None


def database_source():
    kind = st.selectbox("数据库类型", ["SQLite", "MySQL", "PostgreSQL"])
    with st.form(f"connection_{kind}"):
        schema = None
        if kind == "SQLite":
            filename = st.text_input("SQLite 文件路径", placeholder="sales.db")
        else:
            driver, default_port = {
                "MySQL": ("mysql+pymysql", 3306),
                "PostgreSQL": ("postgresql+psycopg", 5432),
            }[kind]
            address, port_field = st.columns([3, 1])
            host = address.text_input("主机", value="localhost")
            port = port_field.number_input("端口", 1, 65535, default_port)
            database = st.text_input("数据库名")
            username = st.text_input("用户名")
            password = st.text_input("密码", type="password")
            if kind == "PostgreSQL":
                schema = st.text_input("Schema（留空使用默认值）").strip() or None
        connect = st.form_submit_button("连接并列出数据表")

    if connect:
        st.session_state.pop("database", None)
        st.session_state.pop("table_result", None)
        try:
            if kind == "SQLite":
                url = sqlite_url(filename)
            else:
                if not all(value.strip() for value in (host, database, username)):
                    raise ValueError("请填写主机、数据库名和用户名。")
                url = URL.create(
                    driver, username=username.strip(), password=password,
                    host=host.strip(), port=int(port), database=database.strip(),
                )
            st.session_state.database = (kind, url, schema, list_tables(url, schema))
        except ValueError as error:
            st.error(str(error))
        except SQLAlchemyError:
            st.error("无法连接或列出数据表。请检查连接参数和数据库权限。")

    connection = st.session_state.get("database")
    if connection is None or connection[0] != kind:
        return None
    _, url, schema, tables = connection
    if not tables:
        st.info("连接成功，当前数据库或 Schema 中没有可选的数据表。")
        return None

    table = st.selectbox("数据表", tables)
    if st.button("读取数据"):
        st.session_state.pop("table_result", None)
        try:
            data = read_table(url, schema, table)
            revision = st.session_state.get("database_revision", 0) + 1
            st.session_state.database_revision = revision
            st.session_state.table_result = (table, data, revision)
        except SQLAlchemyError:
            st.error("读取失败。请检查数据表是否存在以及账号是否有读取权限。")
    result = st.session_state.get("table_result")
    if result is not None and result[0] == table:
        return (kind, table, result[2]), table, result[1]
    return None


def show_analysis(data):
    rows, columns, missing = st.columns(3)
    rows.metric("分析行数", f"{len(data):,}")
    columns.metric("字段数", len(data.columns))
    missing.metric("缺失单元格", f"{data.isna().sum().sum():,}")
    if data.empty:
        st.info("当前工作表或数据表没有数据行。")
        return

    preview, summary, grouping = st.tabs(["数据预览", "统计概要", "分组分析"])
    with preview:
        st.caption("显示前 100 行")
        st.dataframe(data.head(100), hide_index=True)
    numbers = data.select_dtypes(include="number")
    with summary:
        st.dataframe(column_summary(data))
        if len(numbers.columns):
            st.dataframe(numbers.describe().T)
    with grouping:
        group_column = st.selectbox("分组字段", list(data.columns))
        operations = GROUP_OPERATIONS if len(numbers.columns) else GROUP_OPERATIONS[:1]
        operation = st.selectbox("统计方式", operations)
        value_column = None
        if operation != "计数":
            value_column = st.selectbox("数值字段", list(numbers.columns))
        result = group_summary(data, group_column, operation, value_column)
        # 分组字段可能与统计方式同名，展示时使用独立的列名。
        labels = pd.Series(result.index, dtype=object).astype("string").fillna("〈空值〉")
        display = pd.DataFrame({"分组": labels, operation: result.to_numpy()})
        st.dataframe(display, hide_index=True)
        chart = display.dropna(subset=[operation]).head(20)
        if not chart.empty:
            st.caption("柱状图展示统计值最高的 20 组（最多）。")
            st.bar_chart(chart.set_index("分组"))


def main():
    st.set_page_config(page_title="InstructData ChatBI", layout="wide")
    with st.sidebar:
        st.header("数据来源")
        source = st.radio("来源类型", ["Excel 文件", "关系数据库"])
        excel = source == "Excel 文件"
        selection = excel_source() if excel else database_source()

    st.title("InstructData ChatBI")
    if selection is None:
        show_chat(None, (source, None), excel)
        return

    identity, name, data = selection
    st.caption(f"当前数据：{name}")
    if len(data) > ROW_LIMIT:
        st.info(f"当前数据超过 {ROW_LIMIT:,} 行。问答、图表和导出均基于读取到的前 {ROW_LIMIT:,} 行。")
        data = data.head(ROW_LIMIT)
    with st.expander("查看数据与统计"):
        show_analysis(data)
    chat_data = data.copy(deep=False)
    chat_data.columns = chat_data.columns.map(str)
    if not chat_data.columns.is_unique:
        st.error("字段名转换后有重名，请先把字段名改成唯一的文本名称。")
        return
    show_chat(chat_data, (source, identity), excel)
