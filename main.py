from convert_dumps import Dumper, ExtractTable
from lib.dumper import FlatBufferDumper
from resource_downloader import Downloader

downloader = Downloader()
downloader.main()

fb_dumper = FlatBufferDumper()
b = fb_dumper.get_il2cpp_dumper()
fb_dumper.dump_il2cpp(b)

dumper = Dumper()
dumper.dump()
ExtractTable().extract_tables()
