from convert_dumps import Dumper, ExtractTable
from lib.dumper import FlatBufferDumper
from resource_downloader import Downloader

downloader = Downloader()
downloader.main()

fb_dumper = FlatBufferDumper()
fb_dumper.main()

dumper = Dumper()
dumper.dump()
ExtractTable().extract_tables()
