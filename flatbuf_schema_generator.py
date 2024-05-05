import re
import os
import subprocess

# paths

ROOT = os.path.dirname(os.path.realpath(__file__))
DUMP_FP = os.path.join(ROOT, "dump.cs")
FLATC = os.path.join(ROOT, "lib", "flatc.exe")
FBS_FP = os.path.join(ROOT, "BlueArchive.fbs")


def main():
    # fetch whole dump.cs
    with open(DUMP_FP, "rt", encoding="utf-8") as f:
        data = f.read()

    # extract enums
    enums = extract_enums(data)
    # extract structs
    structs = extract_structs(data)

    # create fbs scheme
    with open(FBS_FP, "wt", encoding="utf8") as f:
        # write namespace header
        f.write("namespace FlatData;\n\n")
        # write enums
        write_enums_to_fbs(enums, f)
        # write structs
        write_structs_to_fbs(structs, enums, f)

    # create python wrapper

    # compile fbs schema to python
    print(subprocess.run(f'"{FLATC}" --python --scoped-enums "{FBS_FP}"'))

    # write init file
    init_fp = os.path.join(ROOT, "FlatData", "__init__.py")
    with open(init_fp, "wt", encoding="utf8") as f:
        for fn in os.listdir(os.path.join(ROOT, "FlatData")):
            if fn.endswith(".py") and fn not in ["dump.py", "__init__.py"]:
                f.write("from .{n} import {n}\n".format(n=fn[:-3]))

        # write dump helper
        init_fp = os.path.join(ROOT, "FlatData", "dump.py")
    with open(init_fp, "wt", encoding="utf8") as f:
        create_dumper_wrappers(structs, enums, f)


# regexes

reStruct = re.compile(
    r"""struct (.{0,128}?) :.{0,128}?IFlatbufferObject.{0,128}?
\{
(.+?)
\}
""",
    re.M | re.S,
)
reStructProperty = re.compile(r"""public (.+) (.+?) { get; }""")
reEnum = re.compile(
    r"""// Namespace: FlatData
public enum (.{1,128}?) // TypeDefIndex: \d+?
{
	// Fields
	public (.+?) value__; // 0x0
(.+?)
}""",
    re.M | re.S,
)
reEnumField = re.compile(r"public const (.+?) (.+?) = (-?\d+?);")

reTableDataType = re.compile(r"public Nullable<(.+?)> DataList\(int j\) { }")

types = []


def extract_enums(data):
    enums = {}
    for name, format, field_text in reEnum.findall(data):
        if "." in name:
            continue
        fields = {}
        enum = {"format": format, "fields": fields}
        enums[name] = enum

        for _, fname, num in reEnumField.findall(field_text):
            if num in enum:
                input()
            #     if "duplicates" not in enum:
            #         enum["duplicates"] = []
            #     enum["duplicates"].append([num, fname])
            # else:
            fields[num] = fname
    return enums


def write_enums_to_fbs(enums, f):
    for name, enum in enums.items():
        f.write(
            "enum %s: %s{\n    %s\n}\n\n"
            % (
                name,
                enum["format"],
                ",\n    ".join(
                    f"{key} = {value}" for value, key in enum["fields"].items()
                ),
            )
        )


def extract_structs(data):
    structs = {}
    for key, intern in reStruct.findall(data):
        struct = {}
        for prop in reStructProperty.finditer(intern):
            name, typ = prop[2], prop[1]
            if name in ["ByteBuffer"]:
                continue
            typ_is_list = False
            if len(name) > 6 and name.endswith("Length"):
                list_name = name[:-6]
                match = re.search(f"public (.+?) {list_name}\(int j\) {{ }}", intern)
                if match:
                    typ = match[1]
                    name = list_name
                    typ_is_list = True

            if typ.startswith("Nullable<"):
                typ = typ[9:-1]
            if typ_is_list:
                typ = f"[{typ}]"

            struct[name] = typ

        if struct:
            structs[key] = struct
    return structs


types = ["bool", "byte", "int", "long", "uint", "ulong", "float", "double", "string"]


def write_structs_to_fbs(structs, enums, f):
    for key, struct in structs.items():
        f.write(f"table {key}{{\n")
        for pname, ptype in struct.items():
            if ptype[0] == "[":
                typ = ptype[1:-1]
                if typ.endswith("Length"):
                    typ = typ[:-6]
                if pname == typ:
                    pname += "_"
                if typ not in structs and typ not in enums and typ not in types:
                    continue
            f.write(f"    {pname}: {ptype};\n")
        f.write("}\n\n")


def create_dumper_wrappers(structs, enums, f):
    typ_to_convert = {
        "string": "ConvertString",
        "int": "ConvertInt",
        "long": "ConvertLong",
        "uint": "ConvertUInt",
        "ulong": "ConvertULong",
        "float": "ConvertFloat",
        "double": "ConvertDouble",
    }
    f.write("from lib.TableEncryptionService import *\n\n")
    f.write("def dump_table(obj) -> list:\n")
    f.write("    typ_name = obj.__class__.__name__[:-5]\n")
    f.write(
        "    dump_func = next(f for x,f in globals().items() if x.endswith(typ_name))\n"
    )
    f.write("    password = CreateKey(typ_name[:-5])\n")
    f.write(
        "    return [\n        dump_func(obj.DataList(j), password)\n        for j in range(obj.DataListLength())\n    ]\n\n"
    )
    for name, struct in structs.items():
        if name.endswith("Table"):
            pass
        #    f.write(f"function dump_{name}(obj) -> list:\n")
        #    f.write("    return [obj.DataList(j) for j in range(obj.DataListLength())]\n\n")
        else:
            f.write(f"def dump_{name}(obj, password) -> dict:\n")
            f.write("    return {\n")

            for pname, ptype in struct.items():
                is_list = False
                if ptype[0] == "[":
                    ptype = ptype[1:-1]
                    is_list = True

                if ptype in typ_to_convert:
                    convert = typ_to_convert[ptype]
                    val_func = f"{convert}(obj.{pname}(%s), password)"
                elif ptype in enums:
                    convert = typ_to_convert[enums[ptype]["format"]]
                    val_func = f"{ptype}({convert}(obj.{pname}(%s), password)).name"
                elif ptype == "bool":
                    val_func = f"obj.{pname}(%s)"
                elif ptype in structs:
                    val_func = f"dump_{ptype}(obj.{pname}(%s), password)"
                else:
                    raise NotImplementedError(f"{ptype}")
                if is_list:
                    val_func = f"[{val_func%('j')} for j in range(obj.{pname}Length())]"
                else:
                    val_func = val_func % ""
                f.write(f"        '{pname}': {val_func},\n")
            f.write("    }\n\n")

    f.write("from enum import IntEnum\n\n\n")
    for name, enum in enums.items():
        f.write(f"class {name}(IntEnum):\n")
        for value, key in enum["fields"].items():
            if key == "None":
                key = "none"
            f.write(f"    {key} = {value}\n")
        f.write("\n")


if __name__ == "__main__":
    main()

