from os import path

from lib.compiler import CompileToPython, CSParser
from lib.console import notice, print
from lib.dumper import IL2CppDumper
from utils.config import Config
from utils.util import FileUtils


class FlatbufferExtractor:
    DUMP_PATH = "Dumps"
    IL2CPP_NAME = "libil2cpp.so"
    METADATA_NAME = "global-metadata.dat"

    FB_DATA_DIR = path.join(Config.extract_dir, "FlatData")
    DUMP_CS_FILE_PATH = path.join(Config.extract_dir, DUMP_PATH, "dump.cs")

    def dump(self) -> None:
        """Dump unity lib from il2cpp.so and global-metadata.dat"""
        save_path = Config.temp_dir
        dumper = IL2CppDumper()
        print("Downloading il2cpp-dumper...")
        dumper.get_il2cpp_dumper(save_path)

        il2cpp_path = FileUtils.find_files(Config.temp_dir, [self.IL2CPP_NAME], True)
        metadata_path = FileUtils.find_files(
            Config.temp_dir, [self.METADATA_NAME], True
        )

        if not (il2cpp_path and metadata_path):
            raise FileNotFoundError(
                "Cannot find il2cpp binary file or global-metadata file. Make sure exist."
            )
        abs_il2cpp_path = path.abspath(il2cpp_path[0])
        abs_metadata_path = path.abspath(metadata_path[0])

        extract_path = path.abspath(path.join(Config.extract_dir, self.DUMP_PATH))

        print("Try to dump il2cpp...")
        dumper.dump_il2cpp(extract_path, abs_il2cpp_path, abs_metadata_path)
        notice("Dump il2cpp binary file successfully.")

    def compile(self) -> None:
        """Compile python callable module from dump file"""
        print("Parsing dump.cs...")
        parser = CSParser(self.DUMP_CS_FILE_PATH)
        enums = parser.parse_enum()
        structs = parser.parse_struct()

        print("Generating flatbuffer python dump files...")
        compiler = CompileToPython(enums, structs, self.FB_DATA_DIR)
        compiler.create_enum_files()
        compiler.create_struct_files()
        compiler.create_module_file()
        compiler.create_dump_dict_file()
