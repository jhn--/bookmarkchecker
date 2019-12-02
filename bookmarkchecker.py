#!/usr/bin/env python3

from os import path
import sys
import re
from bs4 import BeautifulSoup
from pprint import pprint
from time import strftime, localtime
import requests
# import threading


class bookmarkChecker():
    """
    bookmarkChecker object
    """
    def __init__(self, bookmark_path):
        """
        initialise bookmarkChecker object
        """
        self.bookmark_path = bookmark_path
        self.details = {}

        with open(self.bookmark_path, 'r') as bm_fp:
            self.soup = BeautifulSoup(bm_fp, 'html.parser')

    @property
    def title(self):
        """
        test function w @property decorator, test function
        """
        return self.soup.title.text
    
    def urlStatus(self):
        """
        even though urlChecker() prints out the url and status 
        """
        for bookmark in self.details:
            print(f'{0}\t|\t{1}').format(bookmark['url'], bookmark['res_code'])

    def populateDetails(self):
        """
        populate bookmarkChecker.details with all hyperlinks in bookmark
        """
        self.bookmark_ahref = self.soup.find_all('a')
        for url in enumerate(self.bookmark_ahref):
            self.details[url[0]] = {}
            self.details[url[0]]['url'] = url[1].get('href')
            self.details[url[0]]['add_date'] = convertEpochtoLocaltime(int(url[1].get('add_date')))
            self.details[url[0]]['title'] = url[1].get_text()

    def urlChecker(self, url, checktimeout=3):
        """
        checks url by sending a request.get() with a timeout of 3 seconds
        """
        print(f'checking url: {url}')
        try:
            r = requests.get(url, timeout=checktimeout)
        except Exception as e:
            status_code = '999'
        else:
            status_code = r.status_code
        finally:
            print(f'checked {url}, status code: {status_code}')
            return str(status_code)

    def checkLinks(self):
        """
        here we will traverse through the links and check if we get any responses from the urls
        """
        for i in self.details:
            # t = threading.Thread(target=self.urlChecker, args=(i['url']))
            self.details[i]['res_code'] = self.urlChecker(self.details[i]['url'])


def convertEpochtoLocaltime(epoch):
    """
    convert epoch time to local time
    """
    return strftime('%Y-%m-%d %H:%M:%S %z', localtime(epoch))


def main():
    if len(sys.argv) != 2:
        print('Need path to bookmark file.')
        print('ie. ')
        print('python3 /path/to/bookmarkchecker.py /path/to/bookmark.html')
        return False
        # exit()
    if path.exists(sys.argv[1]):
        bm_checker = bookmarkChecker(sys.argv[1])
        # print(f'{bm_checker.title}')
        # print(f'{bm_checker.bookmark_path}')
        bm_checker.populateDetails()
        # print(bm_checker.details[0])
        bm_checker.checkLinks()
    else:
        print("{} is not valid".format(sys.argv[1]))


if __name__ == '__main__':
    main()