# Blue Archive asset downloader

A small project that downloads all assets of the global version of Blue Archive and extracts them while it's at it.

The script updates the assets and even its own parameters on its own,
so all you have to do is execute the download_assets.py script after every update to get the latest files.

## Requirements

- Python 3.6+
- UnityPy 1.7.21
- requests
- xxhash
- pycryptodome
- flatbuffers

# Scripts

- ``download_assets.py``
  - 下载素材
- ``extract_tables.py``
  - Extracts and decrypts the tables from the zip files in ``Preload\TableBundles``
  - due to the way it works, this script can take ages, around 15 minutes
- ``flatbuf_schema_generator.py``
  - Generates the flatbuf schemas and python dump wrapper for ``extract_tables.py``

## TODO

- 支持国服/国际服/日服下载
- 支持下载时解包