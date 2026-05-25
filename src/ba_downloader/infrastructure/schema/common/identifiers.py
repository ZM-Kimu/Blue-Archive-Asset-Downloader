from keyword import iskeyword


def make_valid_identifier(variable_name: str) -> str:
    if not variable_name:
        return "_"
    if variable_name[0].isdigit():
        variable_name = "_" + variable_name
    if iskeyword(variable_name):
        variable_name = f"{variable_name}_"
    return variable_name
