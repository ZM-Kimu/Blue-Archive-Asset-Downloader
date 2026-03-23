import math
from keyword import kwlist
from threading import Thread
from typing import Any, Generator


class Utils:
    @staticmethod
    def create_thread(target_func: Any, thread_pool: list[Thread], *args, **kwargs) -> None:
        thread = Thread(target=target_func, args=args, kwargs=kwargs)
        thread.start()
        thread_pool.append(thread)

    @staticmethod
    def convert_name_to_available(variable_name: str) -> str:
        if not variable_name:
            return "_"
        if variable_name[0].isdigit():
            variable_name = "_" + variable_name
        if variable_name in kwlist:
            variable_name = f"{variable_name}_"
        return variable_name

    @staticmethod
    def seperate_list_as_blocks(content: list, block_num: int) -> Generator[list, Any, None]:
        for index in range(0, len(content), math.ceil(len(content) / block_num)):
            yield content[index : index + math.ceil(len(content) / block_num)]


class TemplateString:
    def __init__(self, template: str) -> None:
        self.template = template

    def __call__(self, *args: Any) -> str:
        return self.template % args
