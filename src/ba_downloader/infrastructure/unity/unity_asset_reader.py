from typing import Any


class UnityAssetReader:
    @staticmethod
    def search_objects(
        pack_path: str,
        data_type: list[str] | None = None,
        data_name: list[str] | None = None,
        condition_connect: bool = False,
        read_obj_anyway: bool = False,
    ) -> list[Any]:
        data_list: list[Any] = []
        type_passed = False
        try:
            import UnityPy

            environment = UnityPy.load(pack_path)
            for obj in environment.objects:
                if data_type and obj.type.name in data_type:
                    if condition_connect:
                        type_passed = True
                    else:
                        data_list.append(obj)
                if read_obj_anyway or type_passed:
                    data = obj.read()
                    if data_name and data.m_Name in data_name:
                        if not (condition_connect or type_passed):
                            continue
                        data_list.append(obj)
        except Exception:
            return []
        return data_list
