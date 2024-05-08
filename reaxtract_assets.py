import os
from AssetsDownloader import ROOT, RAW, EXT
import AssetBatchConverter

AssetBatchConverter.DST = EXT


for root, dirs, files in os.walk(RAW):
    for f in files:
        if not f.endswith(".bundle"):
            continue
        fp = os.path.join(root, f)
        print(f"{f} done!")
        AssetBatchConverter.extract_assets(fp)
