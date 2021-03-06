# -*- coding: utf-8 -*-

from custom_path import DATA_PATH, CHAT_PATH
from utill import try_except_with_sleep, get_driver, iso2sec
from BaseCrawler import BaseCrawler
from WriterWrapper import WriterWrapper
from time import sleep, time
from multiprocessing import Process
import csv
import os
import sys
import random
from termcolor import cprint
try:
    from orderedset import OrderedSet
except:
    pass


class ChatCrawler(BaseCrawler):

    def __init__(self, config_file_path: str, video_speed_rate: float=3.3, interval_to_crawl: int=30):
        """
        :param config_file_path: path of .ini file
            config.ini
                [Driver]
                PATH="Something"
        :param video_speed_rate: video speed
        :param interval_to_crawl: interval to crawl in sec

        We will recommend that interval_to_crawl * video_speed_rate < 2*60 ~ 3*60 (2 ~ 3 min)
        """
        super().__init__(config_file_path)
        self.urls = []
        self.prefix = 'Chat'
        self.fieldnames = ['time_stamp', 'author_name', 'message', 'img']
        self.chat_iframe = None
        self.video_speed_rate = video_speed_rate
        self.interval_to_crawl = interval_to_crawl

        if video_speed_rate * interval_to_crawl >= 2*60:
            print('We recommend that interval_to_crawl * video_speed_rate < 2*60 ~ 3*60 (2 ~ 3 min)',
                  'Yours is {0}'.format(video_speed_rate*interval_to_crawl))

    def get_urls(self) -> csv.DictReader:
        video_url_filename = [os.path.join(DATA_PATH, f) for f in os.listdir(DATA_PATH)
                              if f.startswith('VideoURL')][0]
        reader = csv.DictReader(open(video_url_filename, 'r', encoding='utf-8'))
        return reader

    @try_except_with_sleep
    def turn_off_autoplay(self):
        sleep(0.3)
        btn_turn_off = self.driver.find_element_by_id('improved-toggle')
        btn_turn_off.click()

    @try_except_with_sleep
    def mute(self):
        btn_mute = self.driver.find_element_by_class_name('ytp-mute-button')
        btn_mute.click()

    @try_except_with_sleep
    def speed_up(self):
        self.driver.execute_script(
            'document.getElementsByTagName("video")[0].playbackRate = {0}'.format(self.video_speed_rate)
        )

    @try_except_with_sleep
    def show_timestamp(self):
        btn_top = self.driver.find_element_by_css_selector('#overflow')
        btn_top.click()
        sleep(0.5)
        btn_bottom = self.driver.find_element_by_css_selector('#items > ytd-menu-service-item-renderer')
        btn_bottom.click()

    @try_except_with_sleep
    def click_show_more(self):
        btn_show_more = self.driver.find_element_by_css_selector('#show-more')
        if btn_show_more.is_displayed():
            btn_show_more.click()

    @try_except_with_sleep
    def click_play_toggle(self):
        self.driver.switch_to.default_content()
        sleep(0.3)
        btn_play = self.driver.find_element_by_css_selector('.ytp-play-button')

        # If video is finished, do not click.
        if btn_play.get_attribute('title') != '다시보기':
            btn_play.click()
            sleep(0.3)
        self.driver.switch_to.frame(self.chat_iframe)

    def get_element_by_id(self, parent_emt, html_id):
        r_emt = parent_emt.find_element_by_id(html_id)
        return r_emt

    def run(self):
        for url_dict in self.get_urls():
            self.run_one(url_dict)

    def run_one(self, url_dict: dict) -> list:
        """
        :param url_dict: {'title', 'video_url', 'time'}
        :return: list of dict {'time_stamp', 'author_name', 'message', 'img'}
        """
        title, video_url, play_time = url_dict['title'], url_dict['video_url'], url_dict['time']
        time_in_sec = iso2sec(play_time)

        wait_to_start, wait_to_crawl = 50*random.random()*random.random(), random.randrange(5, 8)
        cprint('P{0} | {4} | Begin | {1} | wait_to_start: {2}, wait_to_crawl: {3}'.format(
            os.getpid(), title, wait_to_start, wait_to_crawl, play_time
        ), 'green')

        sleep(wait_to_start)

        self.driver = get_driver(self.config_file_path)
        self.driver.get(video_url)

        sleep(wait_to_crawl)

        self.mute()
        self.turn_off_autoplay()
        self.speed_up()

        self.chat_iframe = self.driver.find_element_by_css_selector('#chatframe')
        self.driver.switch_to.frame(self.chat_iframe)

        self.show_timestamp()

        self.click_show_more()

        self.driver.set_window_position(-1800, 0)

        r_set = OrderedSet()
        epochs = int(time_in_sec/self.video_speed_rate/self.interval_to_crawl) + 1
        for i in range(epochs):

            sleep(self.interval_to_crawl)

            # Pause
            self.click_play_toggle()

            start_time = time()
            for chat_emt in self.driver.find_elements_by_css_selector('yt-live-chat-text-message-renderer'):

                try:
                    content_emt = chat_emt.find_element_by_id('content')
                    time_stamp = self.get_element_by_id(content_emt, 'timestamp')
                    author_name = self.get_element_by_id(content_emt, 'author-name')
                    message = self.get_element_by_id(content_emt, 'message')
                    img = self.get_element_by_id(chat_emt, 'img')
                    img_src = img.get_attribute('src') if img != 'Error' else 'Error'
                    r_set.add((time_stamp.text, author_name.text, message.text, img_src))

                except Exception as e:
                    print('Fatal Error: {0}'.format(title), str(e), file=sys.stderr)
                    self.driver.switch_to.default_content()
                    self.driver.close()
                    return []

            time_to_crawl_in_one_epoch = time() - start_time
            print('P{5} | {6} | Interval {1}/{4}, {2} chats | {0} | {3}s'.format(
                title, i + 1, len(r_set), time_to_crawl_in_one_epoch, epochs, os.getpid(), play_time,
            ))

            # Resume
            self.click_play_toggle()

        self.driver.switch_to.default_content()
        self.driver.close()
        cprint('P{0} | {2} | End | {1}'.format(os.getpid(), title, play_time), 'blue')

        return [{
            'time_stamp': tup[0],
            'author_name': tup[1],
            'message': tup[2],
            'img': tup[3],
        } for tup in r_set]

    def export(self):
        urls = self.get_urls()
        for url_dict in urls:
            self.export_one(url_dict)

    def export_one(self, url_dict):
        # Run until its success.
        attempt_counts = 0
        result_run_one = []

        while len(result_run_one) == 0:
            result_run_one = self.run_one(url_dict)
            attempt_counts += 1

            if attempt_counts >= 8:
                cprint('{0} | Error, attempt_counts >= 8'.format(url_dict['title']), 'red')
                break

        # Write
        writer = WriterWrapper(os.path.join(CHAT_PATH, '_'.join([self.prefix, url_dict['title'], url_dict['time']])),
                               self.fieldnames)
        for line in result_run_one:
            writer.write_row(line)
        writer.close()

    def export_with_multiprocess(self, processes=4, resume_interval_in_min=5):
        print('Start crawling with {0} processes'.format(processes))

        process_list = []

        for url_dict in self.get_urls():
            process = Process(target=self.export_one, args=(url_dict,))
            process.start()
            process_list.append(process)

            while len(process_list) >= processes:
                sleep(60*resume_interval_in_min)
                process_list = [process for process in process_list if process.is_alive()]

        for process in process_list:
            process.join()

        print('Crawling ends')


if __name__ == '__main__':
    crawler = ChatCrawler('./config.ini')
    crawler.export_with_multiprocess(
        processes=4,
        resume_interval_in_min=1,
    )
