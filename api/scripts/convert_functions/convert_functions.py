import os.path
import aspose.words as aw
import re
from pydantic import BaseModel,create_model
from typing import Optional

def clean_text(text: str) -> str:
    """
    Function for clearing text from docx and e.t.c. formats
    :param text: input text str
    :return: clean text str
    """
    text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()
def convert_to_text(file_list: list, file_num: int) -> str:
    """
    Function for converting file from list of links use in cycle to use on whole list.
    :param file_list: list with links to cv
    :param file_num: num of cv in list
    :return: text of file_num cv
    """
    lines_to_remove = [
        """Created with an evaluation copy of Aspose.Words. To remove all limitations, you can use Free Temporary 
        License  HYPERLINK "https://products.aspose.com/words/temporary-license/" 
        https://products.aspose.com/words/temporary-license/""",
        "Evaluation Only. Created with Aspose.Words. Copyright 2003-2025 Aspose Pty Ltd."
        ]
    file = file_list[file_num]
    _, ext = os.path.splitext(file)
    ext = ext.lower()
    if ext in [".doc", ".docx", ".rtf", ".pdf"]:
        try:
            doc = aw.Document(str(file))
            text = doc.get_text()
            text = text.splitlines()
            filtered_text = [line for line in text if line.strip() not in lines_to_remove]
            filtered_text = '\n'.join(filtered_text)
            return clean_text(filtered_text)
        except Exception as e:
            raise f"Ошибка при обработке {file}:{e}"
def convert_to_dict(file: str) -> dict:
    """
    Function for converting cv describe to dict with key and values
    :param file: selected path to the cv info
    :return: dictionary formed from table from cv info where first column is key and second if values
    """
    doc = aw.Document(file)
    tables = doc.get_child_nodes(aw.NodeType.TABLE, True)
    if not tables:
        raise ValueError(f"В {file} нет таблиц")

    table = tables[0].as_table()
    result = {}

    for row in table.rows:
        row = row.as_row()
        cells = row.cells
        key = clean_text(cells[0].get_text())
        value = clean_text(cells[1].get_text())

        if key and value:   # <--- добавляем только если оба не пустые
            result[key] = value
        if "Название" in result:
            vacancy_name = result["Название"]
    return result, vacancy_name