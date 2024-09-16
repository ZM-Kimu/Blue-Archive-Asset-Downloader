import sys
import threading
import time
from builtins import print as builtin_print
from datetime import timedelta
from shutil import get_terminal_size
from typing import Literal


class Console:
    _instance: "Console" = None  # type: ignore
    _lock = threading.Lock()
    message_thread: threading.Thread
    previous_text_width = 0
    message = "Initialize..."
    running = False

    # Unique instance in process.
    def __new__(cls, *args, **kwargs) -> "Console":
        if not cls._instance:
            cls._instance = super(Console, cls).__new__(cls, *args, **kwargs)
            cls._instance.running = True
            cls._instance.message_thread = threading.Thread(
                target=cls._instance._start_message, daemon=True
            )
            cls._instance.message_thread.start()

        return cls._instance

    # Console daemon.
    def _start_message(self) -> None:
        spinner = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        spinner_index = 0
        text_index = 0

        terminal_width = get_terminal_size().columns

        while self.running:
            with self._lock:
                text = self.message

            spinner_char = spinner[spinner_index]
            spinner_index = (spinner_index + 1) % len(spinner)

            text_width = sum(4 if ord(c) > 127 else 1 for c in text)

            if text_width > terminal_width - 2:
                space = text_width - len(text)
                display_text = text[text_index:] + " " + text[:text_index]
                display_text = display_text[: terminal_width - space - 2]
                text_index = (text_index + 1) % len(text)
            else:
                if self.previous_text_width > text_width:
                    sys.stdout.write(f"\r{' ' * terminal_width}")
                display_text = text

            sys.stdout.write(
                f"\r{spinner_char} {display_text.ljust(terminal_width-text_width)}\r"
            )
            sys.stdout.flush()

            self.previous_text_width = text_width

            time.sleep(0.1)

    def internal_update_message(self, new_message: str) -> None:
        with self._lock:
            self.message = str(new_message).strip("\n")

    @staticmethod
    def print_notice(notice: str, mode: Literal["warn", "error"]) -> None:
        notice_symbol = "!" if mode == "warn" else "X"
        sys.stdout.write(f"\r{' ' * get_terminal_size().columns}")
        builtin_print(f"{notice_symbol} {notice}")

    @staticmethod
    def update_message(new_message: str) -> None:
        if Console._instance is None:
            Console()
        Console._instance.internal_update_message(new_message)

    def stop(self):
        self.running = False
        sys.stdout.write("\r\n")
        sys.stdout.flush()


# Basic progress bar.
class ProgressBar:
    _instance = None
    _lock = threading.Lock()

    def __init__(
        self, total: int, note: str = "", unit: str = "MB", unit_size: int = 1
    ) -> None:
        self._progress_counter = 0
        self._interrupter = False
        self._item_text = ""
        self.total = total
        self.note = note
        self.unit = unit
        self.unit_size = unit_size
        ProgressBar._instance = self  # Set to static instance when create instance.

    # @classmethod
    # def instance(
    #    cls, total: int, note: str = "", unit: str = "MB", unit_size: int = 1
    # ) -> "ProgressBar":
    #    with cls._lock:
    #        if cls._instance is None:
    #            cls._instance = cls(total, note, unit, unit_size)
    #        return cls._instance

    def __progress_bar(self) -> None:
        start_time = time.time()
        last_update_time = 0.0
        data_size_since_last_update = 0
        rolling_position = 0
        last_message = ""

        while not self._interrupter:
            now = time.time()
            if now - last_update_time > 0.5:
                percent = self._progress_counter / self.total * 100
                bar_length = 20
                filled_length = int(
                    round(bar_length * self._progress_counter / float(self.total))
                )
                bar = "=" * filled_length + ">" + " " * (bar_length - filled_length)
                remaining_time = timedelta(
                    seconds=(self.total - self._progress_counter)
                    / (self._progress_counter / (now - start_time + 0.01) + 0.01)
                ).seconds
                rolling_position = (
                    rolling_position + 1
                    if bar_length + rolling_position < len(self._item_text)
                    and self._item_text == last_message
                    else 0
                )
                print(
                    f"[{bar}] {int(self._progress_counter/self.unit_size)}/{int(self.total/self.unit_size)}  {self._item_text[rolling_position:bar_length + rolling_position]}  {((self._progress_counter - data_size_since_last_update) / self.unit_size / (now - last_update_time + 0.01)):0.2f} {self.unit}/s  {percent:.2f}%  {(remaining_time // 3600):02d}:{(remaining_time % 3600 // 60):02d}:{(remaining_time % 60):02d}  {self.note}"
                )
                last_update_time = now
                data_size_since_last_update = self._progress_counter
                last_message = self._item_text
            time.sleep(0.1)
        self._progress_counter = 0

    @staticmethod
    def increase(value: int = 1) -> None:
        if ProgressBar._instance is not None:
            ProgressBar._instance._increase_value(value)

    @staticmethod
    def item_text(message: str) -> None:
        if ProgressBar._instance is not None:
            ProgressBar._instance._set_item_text(message)

    def _increase_value(self, value: int = 1) -> None:
        self._progress_counter += int(value)

    def _set_item_text(self, message: str) -> None:
        self._item_text = str(message)

    def stop(self) -> None:
        self._interrupter = True
        time.sleep(0.2)

    def __enter__(self) -> "ProgressBar":
        self._interrupter = False
        self.thread = threading.Thread(target=self.__progress_bar)
        self.thread.start()
        return self

    def __exit__(self, *_) -> None:
        self.stop()
        self.thread.join()


def bar_increase(value: int = 1) -> None:
    ProgressBar.increase(value)


def bar_text(message: str) -> None:
    ProgressBar.item_text(message)


def notice(notice: str, type: Literal["warn", "error"] = "warn") -> None:
    Console.print_notice(notice, type)


def print(new_message: str) -> None:
    Console.update_message(new_message)
