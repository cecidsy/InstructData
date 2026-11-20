"""把演示用的销售记录写入 Excel 和 SQLite。"""

import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

from openpyxl import Workbook


def main():
    folder = Path(tempfile.mkdtemp(prefix="instructdata-demo-"))
    excel_path = folder / "sales.xlsx"
    database_path = folder / "sales.db"
    rows = [("华东", 120), ("华南", 80), ("华东", 200)]

    with closing(sqlite3.connect(database_path)) as connection, connection:
        connection.execute("CREATE TABLE sales (region TEXT, amount INTEGER)")
        connection.executemany("INSERT INTO sales VALUES (?, ?)", rows)

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "sales"
    sheet.append(("region", "amount"))
    for row in rows:
        sheet.append(row)
    workbook.save(excel_path)

    print(f"Excel  {excel_path}")
    print(f"SQLite {database_path}")


if __name__ == "__main__":
    main()
