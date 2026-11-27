import csv
import json
from io import BytesIO, StringIO
from zipfile import BadZipFile, ZipFile

from python_calamine import CalamineError, load_workbook

from app.application.import_export.schedules import ImportIssue
from app.domain.files import MAX_UPLOAD_BYTES

csv.field_size_limit(MAX_UPLOAD_BYTES)
CSV_ESCAPED_COLUMNS = "_escaped_text_fields"


def _check_headers(headers):
    names = [name for name in headers if name not in ("", None)]
    if len(names) != len(set(names)):
        raise ValueError("Повторяющиеся заголовки столбцов")


class _CsvRowError(ValueError):
    def __init__(self, row: int, message: str) -> None:
        super().__init__(message)
        self.row = row


def table_rows(content: bytes, extension: str, json_key: str = "entries"):
    if extension == "json":
        data = json.loads(content.decode("utf-8-sig"))
        rows = data.get(json_key) if isinstance(data, dict) else data
        if not isinstance(rows, list):
            raise ValueError("Ожидается массив строк")
        yield from enumerate(rows, 1)
        return
    if extension == "csv":
        data = content.decode("utf-8-sig")
        header = data.partition("\n")[0]
        reader = csv.reader(
            StringIO(data, newline=""), delimiter=";" if ";" in header else ",", strict=True
        )
        index = 1
        try:
            headers = next(reader, [])
            _check_headers(headers)
            while True:
                index = reader.line_num + 1
                row = next(reader, None)
                if row is None:
                    break
                if len(row) > len(headers):
                    yield index, ImportIssue(index, None, "Лишние значения в строке")
                elif row:
                    values = dict(zip(headers, row))
                    for column in values.pop(CSV_ESCAPED_COLUMNS, "").split(","):
                        if column in values and values[column].startswith("'"):
                            values[column] = values[column][1:]
                    yield index, values
        except csv.Error as error:
            raise _CsvRowError(index, str(error)) from error
        return
    with ZipFile(BytesIO(content)) as archive:
        if sum(item.file_size for item in archive.infolist()) > 128 * 1024 * 1024:
            raise ValueError("Распакованная таблица слишком велика")
    with load_workbook(BytesIO(content)) as workbook:
        if not workbook.sheet_names:
            raise ValueError("В файле отсутствует лист")
        sheet = workbook.get_sheet_by_index(0)
        if sheet.height * sheet.width > 1_000_000:
            raise ValueError("Слишком большая область данных таблицы")
        rows = iter(sheet.iter_rows())
        headers = next(rows, [])
        _check_headers(headers)
        for index, row in enumerate(rows, 2):
            if any(value not in (None, "") for value in row):
                yield index, dict(zip(headers, row))


def import_rows(content: bytes, extension: str, json_key: str = "entries"):
    try:
        yield from table_rows(content, extension, json_key)
    except _CsvRowError as error:
        yield error.row, ImportIssue(error.row, "file", str(error))
    except (ValueError, CalamineError, BadZipFile, RecursionError, OverflowError) as error:
        yield None, ImportIssue(None, "file", str(error))
