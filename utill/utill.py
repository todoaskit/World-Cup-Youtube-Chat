import os
import sys
import re
from time import sleep, time
from selenium import webdriver
from typing import List, Callable, Tuple
import configparser


def clean_split(s: str, delimiter='\s+'):
    s = re.sub('[~`!@#$%^&*(),.<>?\-+_=|/\[\]{}]+', ' ', s)
    return re.split(delimiter, s.strip())


def introduce_function(f: Callable):

    def wrapper(*args, **kwargs):
        start_time = time()
        print('Start: {}'.format(f.__name__))
        result = f(*args, **kwargs)
        print('End: {}, {}s consumed'.format(f.__name__, time() - start_time))
        return result

    return wrapper


def is_values_of_key_matched(target_dict: dict, key_dict: dict) -> bool:
    """
    :param target_dict: e.g. 1) {'winner': 'KOR', ...} 2) {'winner': 'GER', ...}
    :param key_dict: e.g. {'winner': 'KOR'}
    :return: e.g. 1) True 2) False
    """

    for key, val in key_dict.items():
        if target_dict[key] != val:
            return False

    return True


def have_enough_words(length: int) -> Callable[[str], bool]:
    """
    :param length: int
    :return: boolean function that return '#words >= length'
    """

    def wrapper(s: str) -> bool:
        return len(s.split()) >= length

    # set the __name__ of wrapper
    w = wrapper
    w.__name__ = 'have_enough_words_{}'.format(str(length))

    return w


def get_readlines(path) -> List[str]:
    return [line for line in open(path, 'r', encoding='utf-8').readlines()]


def get_tsv(path) -> List[Tuple]:
    return [tuple(x.strip().split('\t')) for x in get_readlines(path)]


def get_files(path: str, search_text: str = None) -> list:
    return [f for f in os.listdir(path) if (not search_text) or (search_text in f)]


def get_files_with_dir_path(path: str, search_text: str = None) -> list:
    return [os.path.join(path, f) for f in get_files(path, search_text)]


def try_except(f):
    """
    :param f: function that use this decorator
    :return:
    """
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            print('P{0} | Error: {1}'.format(os.getpid(), f.__name__), e, file=sys.stderr)

    return wrapper


def try_except_with_sleep(f):
    """
    :param f: function that use this decorator
    :return:
    """
    def wrapper(*args, **kwargs):
        try:
            sleep(0.6)
            result = f(*args, **kwargs)
            sleep(0.6)
            return result
        except Exception as e:
            print('P{0} | Error: {1}'.format(os.getpid(), f.__name__), e, file=sys.stderr)

    return wrapper


def get_driver(config_file_path: str) -> webdriver.Chrome:
    """
    :param config_file_path: path of .ini file
        config.ini
            [Driver]
            PATH="Something"
    :return: webdriver.Chrome
    """
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument("--incognito")
    config = configparser.ConfigParser()
    config.read(config_file_path)
    driver = webdriver.Chrome(config['DRIVER']['PATH'], chrome_options=chrome_options)
    driver.implicitly_wait(3)
    return driver


def iso2sec(iso: str) -> int:
    """
    :param iso: e.g. 1:01:02
    :return: sec in int
    """
    arr = iso.split(':')
    len_arr = len(arr)
    if len_arr <= 3:
        arr = ['0'] * (3 - len_arr) + arr
    else:
        raise Exception('len_arr > 3, arr: {}'.format(arr))

    return int(arr[0]) * 60 * 60 + int(arr[1]) * 60 + int(arr[2])


if __name__ == '__main__':
    print(clean_split('123! [wow,]+ {yes} I (am), a - boy.'))
