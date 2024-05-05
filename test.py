import requests
import re

req = requests.get(
    f"https://blue-archive-global.en.uptodown.com/android",)
with open("aa", "w", encoding="utf-8")as f:
    f.write(req.content.decode("utf8"))
