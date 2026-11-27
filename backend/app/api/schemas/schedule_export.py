import csv
import json
from io import BytesIO, StringIO

from odf import teletype
from odf.opendocument import OpenDocumentSpreadsheet
from odf.table import Table, TableCell, TableRow
from odf.text import P
from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE

from app.api.schemas.jobs import ScheduleResponse
from app.api.schemas.schedule_import import ImportedEntry
from app.api.schemas.table_rows import CSV_ESCAPED_COLUMNS
from app.domain.scheduling.schedule import Schedule
from app.domain.shared.errors import InvalidValue


def _csv(columns: list[str], rows: list[list[str]]) -> bytes:
    # Excel может выполнить текстовую ячейку как формулу. Дополнительный столбец
    # позволяет убрать ровно добавленные кавычки при повторном импорте.
    escaped = []
    for row in rows:
        names = []
        for index, value in enumerate(row):
            if value.lstrip().startswith(("=", "+", "-", "@")) or value.startswith(
                ("\t", "\r", "\n")
            ):
                row[index] = "'" + value
                names.append(columns[index])
        escaped.append(",".join(names))
    text = StringIO(newline="")
    writer = csv.writer(text)
    if any(escaped):
        writer.writerow([*columns, CSV_ESCAPED_COLUMNS])
        writer.writerows([*row, names] for row, names in zip(rows, escaped, strict=True))
    else:
        writer.writerow(columns)
        writer.writerows(rows)
    return text.getvalue().encode("utf-8-sig")


def _xlsx(rows: list[list[str]]) -> bytes:
    if any(len(value) > 32767 for row in rows for value in row):
        raise InvalidValue("Значение превышает размер ячейки XLSX", field="file_format")
    book = Workbook(write_only=True)
    sheet = book.create_sheet("Расписание")
    for row in rows:
        cells = []
        for value in row:
            cell = WriteOnlyCell(sheet, value=value)
            cell.data_type = "s"
            cells.append(cell)
        sheet.append(cells)
    output = BytesIO()
    book.save(output)
    return output.getvalue()


def _ods(rows: list[list[str]]) -> bytes:
    document = OpenDocumentSpreadsheet()
    table = Table(name="Расписание")
    document.spreadsheet.addElement(table)
    for row in rows:
        table_row = TableRow()
        table.addElement(table_row)
        for value in row:
            cell = TableCell(valuetype="string")
            paragraph = P()
            teletype.addTextToElement(paragraph, value)
            cell.addElement(paragraph)
            table_row.addElement(cell)
    output = BytesIO()
    document.save(output)
    return output.getvalue()


def encode_schedule(schedule: Schedule, extension: str) -> bytes:
    data = ScheduleResponse.of(schedule).model_dump(mode="json")
    if extension == "json":
        return json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    columns = list(ImportedEntry.model_fields)
    rows = []
    for entry in data["entries"]:
        entry["teachers"] = json.dumps(entry["teachers"], ensure_ascii=False)
        rows.append([entry[name] or "" for name in columns])
    if extension == "csv":
        return _csv(columns, rows)
    if any(
        ILLEGAL_CHARACTERS_RE.search(value) or "\ufffe" in value or "\uffff" in value
        for row in rows
        for value in row
    ):
        raise InvalidValue(
            "Текст содержит символы, недопустимые в XML-таблице", field="file_format"
        )
    if extension == "xlsx":
        return _xlsx([columns, *rows])
    if extension == "ods":
        return _ods([columns, *rows])
    raise ValueError("Неизвестный формат расписания")
