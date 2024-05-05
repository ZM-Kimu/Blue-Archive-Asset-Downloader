# from _typeshed import StrPath
from io import BytesIO
from typing import IO
from zipfile import ZipFile
import os
from .XXHashService import CalculateHash
from typing import Union


class TableZipFile(ZipFile):
    def __init__(self, file: Union[str, BytesIO], name: str = None) -> None:
        super().__init__(file)
        self.password = str(
            CalculateHash(name if not isinstance(file, str) else os.path.basename(file))
        ).encode()

    def open(self, name: str, mode: str = "r", force_zip64=False):
        return super(self.__class__, self).open(
            name, mode, pwd=self.password, force_zip64=force_zip64
        )
