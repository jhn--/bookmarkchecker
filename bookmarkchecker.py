#!/usr/bin/env python3

from os import path
import sys
import re
import requests
import json
# import click
# from pprint import pprint
from collections import OrderedDict

HTTP_CODES = [200, 201, 202, 203, 204, 205, 206, 207, 208, 226, 300, 301, 302, 303, 304, 305, 306, 307, 308, 400, 401, 402, 403, 404, 405, 406, 407, 408, 409, 410, 411, 412, 413, 414, 415, 416, 417, 418, 420, 422, 423, 424, 425, 426, 428, 429, 431, 444, 449, 450, 451, 499, 500, 501, 502, 503, 504, 505, 506, 507, 508, 509, 510, 511, 598, 599]

# contents of the exported bookmark file
BOOKMARK_CONTENTS = ''

def jsonDefault(OrderedDict):
    return OrderedDict.__dict__


class bookmark(object):
    """docstring for bookmark."""

    def __init__(self, name):
        # url of web site
        self.name = name
        # if the url is online and reachable.
        self.isonline = False
        # HTTP response code of request.
        self.response_code = ''
        # Store exception message.
        self.exception_msg = ''

    def __repr__(self):
        return json.dumps(self, default=jsonDefault, indent=4)

    def update_isonline(self, boolean):
        self.isonline = boolean


class bookmarkchecker(object):
    """docstring for bookmarkchecker."""

    def __init__(self, bookmark_path, export_path):
        # file path of exported bookmark file
        self.bookmark_path = bookmark_path
        # data structure which contains the bookmarks
        self.bookmark_repo = {}
        # id for records in bookmarkchecker's repo, always start from 0.
        self.bookmark_id = 0
        # number of bookmarks
        self.numofbookmarks = 0
        # checker results export path
        self.export_path = export_path

    def openbookmark(self):
        '''
        Open exported bookmark file.
        '''
        global BOOKMARK_CONTENTS
        with open(self.bookmark_path, 'r') as fp:
            BOOKMARK_CONTENTS = fp.read()
        fp.close()

    def getbookmarklinks(self):
        '''
        Extract links from exported bookmark file and populate bookmark_repo
        '''
        # print(BOOKMARK_CONTENTS)
        regex = "(?<=A HREF=\")(.*)(?=\" ADD_DATE)"
        matches = re.findall(regex, BOOKMARK_CONTENTS, re.MULTILINE | re.IGNORECASE)

        for match in matches:
            print(match)
            self.bookmark_repo[self.bookmark_id] = bookmark(match)
            self.bookmark_id += 1

        self.numofbookmarks = len(self.bookmark_repo)

    def checkbookmarks(self):
        checker_timeout = 5
        checker_headers = {'user-agent': 'bookmarkchecker/0.1'}
        for key in self.bookmark_repo.keys():
            print("checking link {}/{} : {} -".format(key+1, self.numofbookmarks, self.bookmark_repo[key].name))
            try:
                checkonline = requests.get(self.bookmark_repo[key].name, timeout=checker_timeout, headers=checker_headers)
                self.bookmark_repo[key].response_code = checkonline.status_code
                # print(checkonline.status_code)
                if checkonline.status_code in HTTP_CODES:
                    self.bookmark_repo[key].update_isonline(True)
            except Exception as e:
                self.bookmark_repo[key].exception_msg = e
            finally:
                print('{} {}'.format(key, self.bookmark_repo[key]))

#     def repo_contents(self):
#         for key in self.bookmark_repo.keys():
#             print('{}, {} \n'.format(key, self.bookmark_repo[key]))
#             print('\n')

    def __repr__(self):
        return json.dumps(self, default=jsonDefault, indent=4)

    def export_results(self):
        # skipping checks for now
        print('exporting results -\n')
        with open(self.export_path, 'w+') as json_fp:
            json.dump(self.bookmark_repo, json_fp)
        return True

    # def check_export_path(self, export_path):
    #     if path.isfile(export_path):
    #         self.export_path = export_path
    #         return True
    #     else:
    #         print('check_export_path: File or path not found.')
    #         return False
    #         raise SystemExit
    #         raise FileNotFoundError('check_export_path: File or path not found.')


# @click.command()
# @click.option('--help', )

    # def returnlen(self):
    #     return len(self.bookmark_repo)

    # def returnlastelement(self):
    #     return self.bookmark_repo[5344]


def main():
    if len(sys.argv) != 3:
        print('Need path to bookmark file and exported json file.')
        print('ie. ')
        print('python3 /path/to/bookmarkchecker.py /path/to/bookmark.html /path/to/resultsfile')
        exit()
    if path.exists(sys.argv[1]):
        if path.exists(sys.argv[2]):
            bm_checker = bookmarkchecker(sys.argv[1], sys.argv[2])
            # bm_checker.check_export_path(result_export)
            bm_checker.openbookmark()
            # print("blah {}".format(BOOKMARK_CONTENTS))
            bm_checker.getbookmarklinks()
            bm_checker.checkbookmarks()
            bm_checker.export_results()
        print("{} is not valid".format(sys.argv[2]))
    else:
        print("{} is not valid".format(sys.argv[1]))


if __name__ == '__main__':
    main()
