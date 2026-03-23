from dataclasses import dataclass
from typing import Any


@dataclass
class CharacterData:
    character_id: int
    dev_name: str = ""
    names: list[str] | None = None
    file_name: set[str] | None = None
    cv: str = ""
    age: int = 0
    height: int = 0
    birthday: str = ""
    illustrator: str = ""
    school_en: str = ""
    club_en: str = ""

    @staticmethod
    def serialize(obj: Any) -> Any:
        if isinstance(obj, set):
            return list(obj)
        raise TypeError(f"Type {type(obj)} not serializable")


@dataclass
class CharacterRelation:
    version: str
    relations: list[CharacterData]
