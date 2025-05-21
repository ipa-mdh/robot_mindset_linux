import anyio
from nicegui import ui

def controlled_task(semaphore, acquire_timeout=1, run_timeout=15):
    def decorator(func):
        async def wrapper(*args, **kwargs):
            try:
                with anyio.fail_after(acquire_timeout):
                    await semaphore.acquire()
            except TimeoutError:
                ui.notify('System busy, try again later.')
                return False

            try:
                with anyio.fail_after(run_timeout):
                    return await func(*args, **kwargs)
            except TimeoutError:
                ui.notify('Task timed out and was stopped.')
                return False
            finally:
                semaphore.release()
        return wrapper
    return decorator

