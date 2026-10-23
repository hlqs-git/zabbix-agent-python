from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from .models import CollectionResult


def collect_tasks(tasks, workers):
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(function): name for name, function in tasks}
        for future in as_completed(futures):
            try:
                yield CollectionResult(metrics=future.result())
            except Exception as exc:
                yield CollectionResult(errors=['{}: {}: {}'.format(futures[future], type(exc).__name__, exc)])


@contextmanager
def process_lock(path):
    import fcntl
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a') as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            yield False
            return
        try:
            yield True
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)
