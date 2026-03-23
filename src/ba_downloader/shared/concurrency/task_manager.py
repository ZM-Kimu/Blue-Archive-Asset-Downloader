import concurrent.futures
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from threading import Event, Lock, Thread
from time import sleep
from typing import Any, Callable, Iterable, Literal, Protocol


class TaskManager:
    class TaskManagerWorkerProtocol(Protocol):
        def __call__(self, task_manager: "TaskManager", *args: Any, **kwargs: Any) -> None:
            ...

    def __init__(
        self,
        target_workers: int,
        max_workers: int,
        worker: TaskManagerWorkerProtocol,
        tasks: Queue[Any] = Queue(),
    ) -> None:
        self.target_workers = target_workers
        self.max_workers = max_workers
        self.worker = worker
        self.tasks = tasks
        self.stop_task = False
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.futures: list[concurrent.futures.Future] = []
        self.lock = Lock()
        self.event = Event()
        self.conditional_event = Event()
        self.__cancel_callback: tuple[Callable, tuple] | None = None
        self.__pool_condition: Callable[[], bool] = lambda: self.tasks.empty() or self.stop_task
        self.__force_exit = False

    def __enter__(self) -> "TaskManager":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        is_force = self.stop_task or self.__force_exit
        self.executor.shutdown(wait=not is_force, cancel_futures=is_force)

    def __set_conditions(self, func: Callable[[], bool] | None = None) -> None:
        self.__pool_condition = func or (lambda: self.tasks.empty() or self.stop_task)

    def add_worker(self, *args: Any) -> None:
        future = self.executor.submit(self.worker, self, *args)
        self.futures.append(future)

    def increase_worker(self, num: int = 1) -> None:
        self.target_workers += num

    def set_cancel_callback(self, callback: Callable[..., None], *args: Any) -> None:
        self.__cancel_callback = (callback, args)

    def set_force_shutdown(self, force: bool = True) -> None:
        self.__force_exit = force

    def set_relation(
        self,
        mode: Literal["shut", "constraint"],
        master_manager: "TaskManager",
    ) -> None:
        if mode == "shut":
            self.conditional_event = master_manager.event
            self.__set_conditions(
                lambda: self.stop_task
                or (self.tasks.empty() and self.conditional_event.is_set())
            )

    def import_tasks(self, tasks: Iterable[Any]) -> None:
        queue_tasks: Queue[Any] = Queue()
        for task in tasks:
            queue_tasks.put(task)
        self.tasks = queue_tasks

    def run_without_block(self, *worker_args: Any) -> Thread:
        thread = Thread(target=self.run, args=worker_args, daemon=True)
        thread.start()
        return thread

    def run(self, *worker_args: Any) -> None:
        try:
            while not self.__pool_condition():
                while len(self.futures) < self.target_workers:
                    self.add_worker(*worker_args)
                self.futures = [future for future in self.futures if not future.done()]
                sleep(0.1)
        except KeyboardInterrupt:
            if self.__cancel_callback:
                self.__cancel_callback[0](*self.__cancel_callback[1])
            self.stop_task = True
            while not self.tasks.empty():
                self.tasks.get()
                self.tasks.task_done()
            self.executor.shutdown(wait=False, cancel_futures=True)
        finally:
            self.event.set()
            if not self.__force_exit:
                for future in self.futures:
                    future.result()

    def done(self) -> None:
        self.__exit__(None, None, None)
