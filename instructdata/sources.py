"""把 Excel 工作表和数据库表读取为 DataFrame。"""

import json
from contextlib import contextmanager
from pathlib import Path

import pandas as pd
from sqlalchemy import MetaData, Table, URL, create_engine, inspect, select
from sqlalchemy.pool import NullPool

ROW_LIMIT = 10_000
EXCEL_ENGINES = {".xlsx": "openpyxl", ".xls": "xlrd"}


def open_workbook(upload):
    suffix = Path(upload.name).suffix.lower()
    if suffix not in EXCEL_ENGINES:
        raise ValueError("请选择 .xlsx 或 .xls 工作簿。")
    upload.seek(0)
    return pd.ExcelFile(upload, engine=EXCEL_ENGINES[suffix])


def read_sheet(workbook, sheet_name):
    return workbook.parse(sheet_name, nrows=ROW_LIMIT + 1)


def sqlite_url(filename):
    path = Path(filename.strip()).expanduser()
    if not path.is_file():
        raise ValueError("请输入服务器上已存在的 SQLite 文件路径。")
    return URL.create(
        "sqlite",
        database=path.resolve().as_uri(),
        query={"mode": "ro", "uri": "true"},
    )


@contextmanager
def database_connection(url):
    options = {"connect_timeout": 5} if url.get_backend_name() != "sqlite" else {}
    engine = create_engine(url, poolclass=NullPool, connect_args=options, hide_parameters=True)
    try:
        with engine.connect() as connection:
            yield connection
    finally:
        engine.dispose()


def list_tables(url, schema):
    with database_connection(url) as connection:
        return sorted(inspect(connection).get_table_names(schema=schema))


def read_table(url, schema, table_name):
    with database_connection(url) as connection:
        table = Table(
            table_name, MetaData(), schema=schema,
            autoload_with=connection, resolve_fks=False,
        )
        query = select(table)
        if table.primary_key.columns:
            query = query.order_by(*table.primary_key.columns)
        data = pd.read_sql_query(query.limit(ROW_LIMIT + 1), connection)
    for column, dtype in data.dtypes.items():
        if dtype == object:
            # JSON 和数组等数据库字段可能返回不可分组的 Python 容器。
            data[column] = data[column].map(
                lambda value: json.dumps(value, ensure_ascii=False, default=str, sort_keys=True)
                if isinstance(value, (dict, list)) else value
            )
    return data
