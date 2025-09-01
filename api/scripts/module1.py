from openai import OpenAI
from dotenv import load_dotenv
import os
from api.scripts.convert_functions import pydantic_class, prompt, convert_functions
import time

load_dotenv()
api_key = os.getenv("OPENROUTER_API_KEY")
if not api_key:
    raise ValueError("Не найден API ключ OPENROUTER_API_KEY")

def cv_validation(folder_cv_path: str, info_cv_path: str) -> dict:
    """
    Function for validating all cv hr loaded to folder_cv_path via info about vacancy
    :param folder_cv_path:  folder with all CV loaded for selected info_cv
    :param info_cv_path:  path for vacancy describe
    :return: result dict {link_to_cv:{answer:bool, comment:str, name:str}}, additionally info_dict for module 2
    """
    if not os.path.exists(folder_cv_path):
        raise FileNotFoundError(f"Папка с CV не найдена: {folder_cv_path}")

    if not os.path.exists(info_cv_path):
        raise FileNotFoundError(f"Файл с описанием вакансии не найден: {info_cv_path}")

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key
        )
    try:
        file_paths = [
            os.path.join(folder_cv_path, file)
            for file in os.listdir(folder_cv_path)
            if os.path.isfile(os.path.join(folder_cv_path, file))
            ]
        if not file_paths:
            raise ValueError(f"Папка {folder_cv_path} пустая или не содержит файлов")
    except Exception as e:
        raise Exception(f"Ошибка при обработке файлов в папке {folder_cv_path}: {e}")
    try:
        info_dict = convert_functions.convert_to_dict(file=info_cv_path)
    except Exception as e:
        raise Exception(f"Ошибка при обработке файла с описанием вакансии {info_cv_path}: {e}")

    result_dict = {}
    for i in range(len(file_paths)):
        file = file_paths[i]
        try:
            info_cv = convert_functions.convert_to_text(file_list=file_paths, file_num=i)
            response = client.chat.completions.parse(
                model="openai/gpt-oss-20b:free",
                messages=prompt.prompt_info_fill(info=info_dict, cv_text=info_cv),
                response_format=pydantic_class.JobPosting,
                temperature=0.2,
                top_p=0.95
                )

            result = response.choices[0].message.parsed
            result_dict[file] = {
                "answer": result.answer,
                "comment": result.comment,
                "name": result.name
                }
            print(f"Обработан файл: {file}")
            print(result)
            time.sleep(1)
        except Exception as e:
            print(f"Ошибка при обработке файла {file}: {e}")
            result_dict[file] = {"error": str(e)}
    return result_dict

