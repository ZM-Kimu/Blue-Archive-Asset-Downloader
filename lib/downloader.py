import os
from time import time
from typing import Literal

import requests  # type: ignore
from cloudscraper import create_scraper

from lib.console import bar_increase, print
from utils.config import Config


class FileDownloader:
    """A robust multi-mode downloader that supports file downloading, error handling with retries."""

    def __init__(
        self,
        url: str,
        *,
        headers: dict | None = None,
        enable_progress: bool = False,
        request_method: Literal["get", "post", "head"] = "get",
        use_cloud_scraper: bool = False,
        **kwargs,
    ) -> None:
        """Initializes the FileDownloader instance with the provided parameters.

        Args:
            url (str): The URL of the remote file to download.
            headers (dict | None, optional): HTTP headers for the request. Defaults to a generic User-Agent {"User-Agent": "Mozilla/5.0"}.
            enable_progress (bool, optional): Enables progress bar updates during file download. Defaults to False.
            request_method (Literal[&quot;get&quot;, &quot;post&quot;], optional): Support to post and get. Defaults to "get".
            kwargs: Allow to config the request configurations.
        """

        self.__max_retries: int = Config.retries
        self.__retried = 0
        self.__result: requests.Response | bool | None = None
        self.__kwargs: dict = kwargs

        self.url = url
        self.headers = headers or {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.6261.95 Safari/537.36"
        }
        self.enable_progress = enable_progress
        self.request_method = request_method
        self.use_cloud_scraper = use_cloud_scraper

    def __download(
        self,
        method: Literal["save", "instance"],
        use_stream: bool = False,
        path: str = "",
    ) -> bool:
        """Handles the actual downloading logic, managing retries and progress bar updates.

        Args:
            method (Literal["save", "instance"]): Specifies the download mode.
                "save": Saves the content to the specified path.
                "instance": Returns the HTTP response object.
            use_stream (bool, optional): Whether to enable streaming for the response. Defaults to False.
            path (str, optional): File path to save the downloaded content when using "save" mode. Defaults to "".

        Returns:
            bool: `True` if the download is successful, `False` otherwise.
        """
        counter = 0
        is_save = method == "save" and path != ""
        if self.__retried > self.__max_retries:
            print(
                f"Max retries exceeded for {self.__max_retries} times with file {os.path.split(self.url)[-1]}."
            )
            return False
        try:
            response: requests.Response = getattr(
                create_scraper() if self.use_cloud_scraper else requests,
                self.request_method,
            )(
                self.url,
                headers=self.headers,
                stream=is_save or use_stream,
                proxies=Config.proxy,
                timeout=10,
                **self.__kwargs,
            )
            if is_save:
                with open(path, "wb") as file:
                    start_time = time()
                    for chunk in response.iter_content(chunk_size=4096):
                        file.write(chunk)
                        counter += len(chunk)
                        bar_increase(len(chunk) if self.enable_progress else 0)
                        if counter < 4096 * (time() - start_time):
                            raise ConnectionError("Downloading too slow. Reset...")
                return True

            if method == "instance":
                self.__result = response
                if self.enable_progress:
                    bar_increase()
                return True

            return False
        except KeyboardInterrupt as e:
            raise KeyboardInterrupt("Download task has been interrupted.") from e
        except:
            self.__retried += 1
            bar_increase(-counter if self.enable_progress else 0)
            return self.__download(method, use_stream, path)

    def save_file(self, path: str) -> bool:
        """Saves the file to the specified path.

        Args:
            path (str): The file path where the downloaded content will be saved.

        Returns:
            bool: `True` if the file was saved successfully, `False` otherwise.
        """
        return self.__download("save", True, path)

    def get_response(
        self, use_stream: bool = False
    ) -> requests.Response | Literal[False]:
        """Retrieves the HTTP response object of the download request.

        Args:
            use_stream_in_response (bool, optional): Enables streaming mode for HTTP responses. Defaults to False.

        Returns:
            requests.Response: The response object if the request is successful.
            False: If the request fails.
        """
        if self.__download("instance", use_stream) and isinstance(
            self.__result, requests.Response
        ):
            return self.__result
        return False

    def get_bytes(self) -> bytes:
        """Retrieves the raw bytes of the response content.

        Returns:
            bytes: The raw bytes of the response content. If the request fails, returns an empty bytes object.
        """
        data = bytes()
        if (
            self.__download("instance")
            and isinstance(self.__result, requests.Response)
            and self.__result.content
        ):
            data = self.__result.content
        return data
