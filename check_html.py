from datetime import datetime
from os import path

def check_title(title):
    if not ('Freelance Jobs - Upwork' in title):
        write_to_logfile(data=title)
        return False
    return True


def check_h1(h1):
    if ('Your connection was interrupted' in h1)\
    or ('Find the best freelance jobs' in h1)\
    or ('Job not found' in h1)\
    or ('This job is a private listing' in h1)\
    or ('Do not apply' in h1)\
    or ('This job is no longer available' in h1):
        write_to_logfile(data=h1)
        return False
    return True


def write_to_logfile(data=''):
    if not path.exists('log.txt'):
        with open('log.txt', 'w'):
            pass
    with open('log.txt', 'at') as file:
        time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        file.write(f'{time}\t{data}\n')
