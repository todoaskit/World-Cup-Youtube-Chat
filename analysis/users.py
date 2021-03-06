from collections import defaultdict
from typing import List, Tuple, Dict, Callable

import os
import pickle
import gensim
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.colors as matcolors
import numpy as np
import random

from sklearn.manifold import TSNE
from custom_path import DATA_PATH
from lang import MultiLangChatDataLoader, li_classify_str
from utill import get_files_with_dir_path, have_enough_words
from WriterWrapper import WriterWrapper
from pprint import pprint

# https://github.com/Mimino666/langdetect
import langdetect as ld


class YoutubeUser:

    def __init__(self, _name, _img):
        self.name: str = _name
        self.img: str = _img

    def get_img_hash(self):
        splited = self.img.split('/')
        return splited[3] + '_' + splited[-3]

    def __eq__(self, other):
        return (other.name == self.name) and (other.get_img_hash() == self.get_img_hash())

    def __hash__(self):
        return (self.name, self.get_img_hash()).__hash__()

    def __repr__(self):
        return '_'.join([self.name, self.get_img_hash()])

    def pseudo_equal(self, o):
        if isinstance(o, str):
            return self.name == o or self.img == o or self.get_img_hash() == o
        elif isinstance(o, YoutubeUser):
            return self == o
        else:
            raise TypeError


class YoutubeUserCollection:

    def __init__(self, _multi_lang_chat_data_loader: MultiLangChatDataLoader,
                 file_name: str = None, target_path: str = None):
        self.multi_lang_chat_data_loader = _multi_lang_chat_data_loader

        if self.load(file_name, target_path):
            return

        self.user_to_match_to_lines = self.get_user_to_match_to_lines()
        self.user_to_lang_to_count = self.get_user_to_lang_to_count()

    def __iter__(self):

        def default_message_criteria_func(message: str):
            criteria = len(message.split()) >= 5 or \
                       (message and sorted(map(len, message.split())).pop() >= 7)
            return criteria

        message_criteria_func: Callable = default_message_criteria_func

        for data_loader in self.multi_lang_chat_data_loader:
            yield [';'.join([
                str(YoutubeUser(line_dict['author_name'], line_dict['img'])),
                line_dict['lang_message']
            ]) for line_dict in data_loader if message_criteria_func(line_dict['message'])]

    def dump(self, file_name: str = None, target_path: str = None):
        file_name = file_name or 'YoutubeUserCollection_{}.pkl'.format(self.multi_lang_chat_data_loader.info)
        target_path = target_path or '../Data'

        if file_name in os.listdir(target_path):
            print('Dump Fail: {} already exists.'.format(file_name))
            return

        with open(os.path.join(target_path, file_name), 'wb') as f:
            self.multi_lang_chat_data_loader = None
            pickle.dump(self, f)
            print('Dumped: {}'.format(file_name))

    def load(self, file_name: str = None, target_path: str = None):
        file_name = file_name or 'YoutubeUserCollection_{}.pkl'.format(self.multi_lang_chat_data_loader.info)
        target_path = target_path or '../Data'
        try:
            with open(os.path.join(target_path, file_name), 'rb') as f:
                loaded: YoutubeUserCollection = pickle.load(f)
                self.user_to_match_to_lines = loaded.user_to_match_to_lines
                self.user_to_lang_to_count = loaded.user_to_lang_to_count
            print('Loaded: {}'.format(file_name))
            return True
        except Exception as e:
            print('Load Fail: {0}.\n'.format(file_name), str(e))
            return False

    def get_lang_list(self) -> list:
        return self.multi_lang_chat_data_loader.get_lang_list()['message_lang']

    def get_user_to_match_to_lines(self) -> Dict[YoutubeUser, Dict[tuple, list]]:
        _user_to_match_to_lines: Dict[YoutubeUser, Dict[tuple, list]] = defaultdict(lambda: defaultdict(list))
        for i, data_loader in enumerate(self.multi_lang_chat_data_loader):
            match_tuple = (
                data_loader.get_label('country_1'),
                data_loader.get_label('country_2'),
                data_loader.get_label('main'),
                len(data_loader),
            )
            for line_dict in data_loader:
                author_name = line_dict['author_name']
                img = line_dict['img']
                youtube_user = YoutubeUser(author_name, img)
                _user_to_match_to_lines[youtube_user][match_tuple].append(line_dict)
        return {k: v for k, v in _user_to_match_to_lines.items()}

    def get_user_to_lang_to_count(self) -> Dict[YoutubeUser, Dict[str, int]]:
        lang_list = self.get_lang_list()
        _user_to_lang_to_count: Dict[YoutubeUser, Dict[str, int]] = defaultdict(lambda: {lang: 0 for lang in lang_list})

        sorted_user_to_match_to_lines = sorted(self.get_user_to_match_to_lines().items(),
                                               key=lambda x: -len(x[1].keys()))
        for _user, _match_to_lines in sorted_user_to_match_to_lines:
            for match, lines in _match_to_lines.items():
                for line in lines:
                    _user_to_lang_to_count[_user][line['lang_message']] += 1
        return {k: v for k, v in _user_to_lang_to_count.items()}

    def export_user_stats(self, criteria_func: Callable = None):
        lang_list = self.get_lang_list()
        fieldnames = ['name', 'matches', 'lines'] + lang_list + ['img']
        writer = WriterWrapper('../Data/Users_{}_{}'.format(
            criteria_func.__name__, self.multi_lang_chat_data_loader.info
        ), _fieldnames=fieldnames)
        for _user, _match_to_lines in self.user_to_match_to_lines:
            row = {
                'name': _user.name,
                'img': _user.img,
                'matches': len(_match_to_lines.keys()),
                'lines': sum([len(x) for x in _match_to_lines.values()]),
            }
            row.update(self.user_to_lang_to_count[_user])
            if (not criteria_func) or criteria_func(row):
                writer.write_row(row)

    def query_match_to_lines_of_user(self, target_user: YoutubeUser or str):
        if isinstance(target_user, str):
            for user, match_to_lines in self.user_to_match_to_lines.items():
                if user.pseudo_equal(target_user):
                    return match_to_lines
        else:
            raise NotImplementedError


def display_tsne(gensim_model, word_list, vector_size=100,
                 size=2, legend_size=6.7):
    arr = np.empty((0, vector_size), dtype='f')
    lang_list = []
    for i, word in enumerate(word_list):
        word_vector = gensim_model[word]
        lang_list.append(word.split(';')[1])
        arr = np.append(arr, np.array([word_vector]), axis=0)

    lang_to_color = dict((lang, '#' + "%06x" % random.randint(0, 0xFFFFFF))
                         for i, lang in enumerate(set(lang_list)))

    colors = np.empty(0, dtype='f')
    for word in word_list:
        lang = word.split(';')[1]
        colors = np.append(colors, lang_to_color[lang])

    # find tsne coords for 2 dimensions
    tsne = TSNE(n_components=2, random_state=0)
    np.set_printoptions(suppress=True)
    y = tsne.fit_transform(arr)

    x_coord = y[:, 0]
    y_coord = y[:, 1]

    plt.scatter(x_coord, y_coord, c=colors, s=size, label=lang_list)

    # Legend
    recs = []
    classes = []
    for lang, color in lang_to_color.items():
        classes.append(lang)
        recs.append(mpatches.Rectangle((0, 0), 1, 1, color=color))
    plt.legend(recs, classes, prop={'size': legend_size})

    plt.xlim(x_coord.min() + 0.00005, x_coord.max() + 0.00005)
    plt.ylim(y_coord.min() + 0.00005, y_coord.max() + 0.00005)
    plt.show()


if __name__ == '__main__':

    description_files = get_files_with_dir_path(DATA_PATH, 'Description')
    multi_lang_chat_data_loader = MultiLangChatDataLoader(
        path=description_files[0],
        label_condition_func=None,
        label_condition_args=tuple(),
        criteria_funcs=(have_enough_words(1), have_enough_words(1)),
        lang_func=li_classify_str,
    )

    if multi_lang_chat_data_loader.is_dump_possible():
        multi_lang_chat_data_loader.dump()

    user_collection = YoutubeUserCollection(multi_lang_chat_data_loader)
    user_collection.dump()

    MODE = 'USER_AND_MSG_LANG_TO_VECTOR'

    if MODE == 'STATS':
        def major(d):
            return (d['lines'] >= 10) and (d['matches'] >= 2)


        user_collection.export_user_stats(criteria_func=major)

    elif MODE == 'QUERY':
        # user_something = 'Anônimo Tutoriais'
        # user_something = 'Jonata Araujo'
        # user_something = 'Carlos Botelho'
        # user_something = 'Só coisa boa'
        # user_something = 'Uruguayo Rey de America'

        # user_something = 'Silverhoney'
        # user_something = 'KO'
        # user_something = 'Arturo Jara'
        user_something = 'chris kim'
        match_to_lines_of_user = user_collection.query_match_to_lines_of_user(user_something)
        line = None
        print('User: {}'.format(user_something))
        for match, lines in match_to_lines_of_user.items():
            print('# ' + '_'.join(map(str, match)))
            for line in lines:
                print('\t', line['lang_message'], line['message'])
        print('lang_author_name: {}'.format(line['lang_author_name']))

    elif MODE == 'USER_AND_MSG_LANG_TO_VECTOR':
        list_user_collection = [list(x) for x in user_collection]

        model = gensim.models.Word2Vec(
            list_user_collection,
            min_count=11,
        )
        model.train(
            list_user_collection,
            total_examples=model.corpus_count,
            epochs=model.epochs,
        )

        print(len(model.wv.vocab))
        display_tsne(model, list(model.wv.vocab))
