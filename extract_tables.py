from lib.TableService import TableZipFile
import os
import json
from lib.StringCipher import Decrypt
from download_assets import EXT
from lib.TableEncryptionService import XOR
import FlatData as FlatData

lower_name_to_module_dict = {
    key.lower(): value for key, value in FlatData.__dict__.items()
}
from FlatData.dump import dump_table

TABLE_FP = os.path.join(EXT, "Preload", "TableBundles")


def main():
    for table_file in os.listdir(TABLE_FP):
        # only process .zip files
        if not table_file.endswith(".zip"):
            continue

        print("==", table_file, "==")

        # create dir for table
        table_dir_fp = os.path.join(TABLE_FP, table_file[:-4])
        os.makedirs(table_dir_fp, exist_ok=True)
        # dump files from zip to dir
        tz = TableZipFile(os.path.join(TABLE_FP, table_file))
        for name in tz.namelist():
            print(name)
            data = tz.read(name)
            # Battle.zip
            # process encryption of those two files
            if name.endswith(".json"):
                if name == "logiceffectdata.json":
                    data = Decrypt(data, "LogicEffectData").encode("utf8")
                elif name == "newskilldata.json":
                    data = Decrypt(data, "NewSkillData").encode("utf8")
            # Excel.zip
            # process encryption and encoding of all excel files
            elif table_file == "Excel.zip":
                try:
                    flatbuffer_cls = lower_name_to_module_dict[name[:-6]]
                    data = XOR(flatbuffer_cls.__name__, data)
                    flatbuffer = flatbuffer_cls.GetRootAs(data)
                    data = json.dumps(
                        dump_table(flatbuffer), indent=4, ensure_ascii=False
                    ).encode("utf8")
                    name = f"{flatbuffer_cls.__name__}.json"
                except Exception as e:
                    print(e)
                    continue
            
            # write to file
            fp = os.path.join(table_dir_fp, name)
            with open(fp, "wb") as f:
                f.write(data)


if __name__ == "__main__":
    main()
