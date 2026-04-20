from dataclasses import dataclass

import anyio
from nicegui import ui


@dataclass
class ControlledTaskResult:
    ok: bool
    timed_out: bool = False
    busy: bool = False
    value: object = None
    message: str = ''


def controlled_task(semaphore, acquire_timeout=1, run_timeout=15):
    def decorator(func):
        async def wrapper(*args, **kwargs):
            try:
                with anyio.fail_after(acquire_timeout):
                    await semaphore.acquire()
            except TimeoutError:
                message = 'System busy, try again later.'
                ui.notify(message)
                return ControlledTaskResult(ok=False, busy=True, message=message)

            try:
                if run_timeout is None:
                    result = await func(*args, **kwargs)
                else:
                    with anyio.fail_after(run_timeout):
                        result = await func(*args, **kwargs)
                if isinstance(result, ControlledTaskResult):
                    return result
                return ControlledTaskResult(ok=bool(result), value=result)
            except TimeoutError:
                message = 'Task timed out and was stopped.'
                ui.notify(message)
                return ControlledTaskResult(ok=False, timed_out=True, message=message)
            finally:
                semaphore.release()
        return wrapper
    return decorator
