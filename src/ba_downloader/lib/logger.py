# This lib is a singleton instance.
import json


class Log:
    LOG_PATH = "log.json"
    DATA: dict = {}

    def __init__(self) -> None:
        pass

    @staticmethod
    def resources(version: str) -> None:
        pass


with open(Log.LOG_PATH, "rt", encoding="utf8") as f:
    Log.DATA = json.load(f)

