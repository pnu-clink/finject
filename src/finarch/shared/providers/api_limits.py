"""Bound HTTP requests shared by case and nested variant workers in this process."""
from contextlib import contextmanager
import threading
api_concurrency = __import__('finarch.dataset.90-operations.schedule_settings', fromlist=['api_concurrency']).api_concurrency

_condition=threading.Condition()
_active=0

@contextmanager
def request_slot():
    global _active
    limit=api_concurrency()
    with _condition:
        _condition.wait_for(lambda:_active<limit)
        _active+=1
    try:
        yield
    finally:
        with _condition:
            _active-=1
            _condition.notify_all()
