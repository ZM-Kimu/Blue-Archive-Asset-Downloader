from dataclasses import dataclass
from os import getcwd
from typing import Literal

Region = Literal["cn", "gl", "jp"]


@dataclass(frozen=True, slots=True)
class AppSettings:
    region: Region
    threads: int = 20
    version: str = ""
    raw_dir: str = "RawData"
    extract_dir: str = "Extracted"
    temp_dir: str = "Temp"
    extract_while_download: bool = False
    resource_type: tuple[str, ...] = ("all",)
    proxy_url: str = ""
    max_retries: int = 5
    search: tuple[str, ...] = ()
    advanced_search: tuple[str, ...] = ()
    work_dir: str = ""

    def normalized(self) -> "AppSettings":
        region = self.region.lower()  # type: ignore[assignment]
        raw_dir = self.raw_dir
        extract_dir = self.extract_dir
        temp_dir = self.temp_dir

        if raw_dir == "RawData":
            raw_dir = f"{region.upper()}{raw_dir}"
        if extract_dir == "Extracted":
            extract_dir = f"{region.upper()}{extract_dir}"
        if temp_dir == "Temp":
            temp_dir = f"{region.upper()}{temp_dir}"

        resource_type = tuple(r.lower() for r in self.resource_type)
        if not resource_type or "all" in resource_type:
            resource_type = ("table", "media", "bundle")

        return AppSettings(
            region=region,
            threads=max(1, self.threads),
            version=self.version,
            raw_dir=raw_dir,
            extract_dir=extract_dir,
            temp_dir=temp_dir,
            extract_while_download=self.extract_while_download,
            resource_type=resource_type,
            proxy_url=self.proxy_url,
            max_retries=max(0, self.max_retries),
            search=tuple(self.search),
            advanced_search=tuple(self.advanced_search),
            work_dir=self.work_dir or getcwd(),
        )
