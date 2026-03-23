import os


class FileUtils:
    @staticmethod
    def find_files(
        directory: str,
        keywords: list[str],
        absolute_match: bool = False,
        sequential_match: bool = False,
    ) -> list[str]:
        paths: list[str] = []
        for directory_path, _, files in os.walk(directory):
            for file in files:
                if absolute_match and file in keywords:
                    paths.append(os.path.join(directory_path, file))
                elif not absolute_match and any(keyword in file for keyword in keywords):
                    paths.append(os.path.join(directory_path, file))

        if not sequential_match:
            return paths

        sorted_paths = []
        for keyword in keywords:
            for file_path in paths:
                if keyword in file_path:
                    sorted_paths.append(file_path)
                    break

        return sorted_paths
