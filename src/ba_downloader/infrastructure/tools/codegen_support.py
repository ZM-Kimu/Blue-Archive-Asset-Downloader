from keyword import kwlist
from typing import Any


def make_valid_identifier(variable_name: str) -> str:
    if not variable_name:
        return "_"
    if variable_name[0].isdigit():
        variable_name = "_" + variable_name
    if variable_name in kwlist:
        variable_name = f"{variable_name}_"
    return variable_name


class TemplateString:
    def __init__(self, template: str) -> None:
        self.template = template

    def __call__(self, *args: Any) -> str:
        return self.template % args
