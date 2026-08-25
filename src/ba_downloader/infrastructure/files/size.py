from rich.filesize import decimal


def format_file_size(size: int) -> str:
    return decimal(size)
