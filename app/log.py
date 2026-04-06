from datetime import timedelta, timezone, datetime

# from actions_toolkit import core


def now():
    tz = timezone(timedelta(hours=+8))
    return datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')


def info(s: str = ''):
    print(f'[{now()}] {s}')
    # core.info(f'[{now()}] {s}')


def warning(s: str = ''):
    print(f'[{now()}] {s}')
    # core.warning(f'[{now()}] {s}')


def error(s: str = ''):
    print(f'[{now()}] {s}')
    # core.info(f'[{now()}] {s}')


def set_failed(s: str = ''):
    print(f'[{now()}] {s}')
    # core.set_failed(f'[{now()}] {s}')
