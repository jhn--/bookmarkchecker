#!/usr/bin/env python3

import asyncio
import sys
from datetime import date, datetime
from os import path
from pprint import pprint
from time import localtime, strftime
from collections import Counter

import aiohttp
from bs4 import BeautifulSoup


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
        self.c = None
        self.bookmarkstats = {}

    @property
    def get_details(self):
        """
        return details
        """
        return self.details

    def urlStatus(self):
        """
        even though urlChecker() prints out the url \
        and status
        """
        for bookmark in self.details:
            print(f"{self.details[bookmark]['url']}\t|\t{self.details[bookmark]['resp_code']}")

    def populateDetails(self):
        """
        populate bookmarkChecker.details with all hyperlinks in bookmark
        """
        with open(self.bookmark_path, 'r') as bm_fp:
            self.soup = BeautifulSoup(bm_fp, 'html.parser')

        self.bookmark_ahref = self.soup.find_all('a')
        for url in enumerate(self.bookmark_ahref):
            self.details[url[0]] = {}
            self.details[url[0]]['url'] = url[1].get('href')
            self.details[url[0]]['add_date'] = {}
            self.details[url[0]]['add_date']['epoch'] = \
                url[1].get('add_date')
            self.details[url[0]]['add_date']['localtime'] = \
                convertEpochtoLocaltime(int(url[1].get('add_date')))
            self.details[url[0]]['title'] = url[1].get_text()
            self.details[url[0]]['resp_code'] = None

    async def urlChecker(self, session, urlid, url, checktimeout=30):
        """
        checks url by sending a request.get() with a timeout of 30 seconds
        """
        # print(f"\033[1;32;40m Checking url: {url}")
        try:
            async with session.request("GET", url, timeout=checktimeout) as r:
                # print(f"\033[1;36;40m url: {url} -->\
                #    status code: {r.status}")
                status = r.status
        except Exception as e:
            # print(f"\033[1;31;40m url: {url} --> error: {repr(e)}")
            status = 999
            self.details[urlid]['exception'] = repr(e)
        finally:
            self.details[urlid]['resp_code'] = status

    async def checkLinks(self):
        """
        here we will traverse through the links and check if we get \
            any responses from the urls
        """
        async with aiohttp.ClientSession() as session:
            tasks = []
            for i in self.details:
                tasks.append(self.urlChecker(
                    session, i, self.details[i]['url'], 30))

            await asyncio.gather(*tasks)

    def getRespCodeStats(self):
        """
        using collections.Counter to get the list of resp_codes and returning them
        # todo - present the data in prettier way
        """
        self.c = Counter([value['resp_code'] for value in self.details.values()])
        return self.c.items()

    @property
    def getBookmarkStats(self):
        """
        shows how many bookmarks were added every year.
        """
        thisyear = date.today().year
        nextyear = None
        for year in range(thisyear, thisyear-10, -1):
            if nextyear is None:
                thisyear_epoch = int(datetime(year, 1, 1 ,0, 0, 0).timestamp())
                bookmarks_in_year = [k[0] for k in self.details.items() if int(k[1]['add_date']['epoch']) >= thisyear_epoch]
            else:
                thisyear_epoch = int(datetime(year, 1, 1 ,0, 0, 0).timestamp())
                nextyear_epoch = int(datetime(nextyear, 1, 1 ,0, 0, 0).timestamp())
                bookmarks_in_year = [k[0] for k in self.details.items() if (int(k[1]['add_date']['epoch']) >= thisyear_epoch and int(k[1]['add_date']['epoch']) < nextyear_epoch)]
            nextyear = year
            self.bookmarkstats[year] = (len(bookmarks_in_year), bookmarks_in_year)
        
        return [(kv[0], kv[1][0]) for kv in self.bookmarkstats.items()]


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
        bm_checker.populateDetails()
        asyncio.get_event_loop().run_until_complete(bm_checker.checkLinks())
        # pprint(bm_checker.get_details)
        # bm_checker.urlStatus()
        # print(bm_checker.getStats())
        print(bm_checker.getRespCodeStats())
        pprint(bm_checker.getBookmarkStats)
    else:
        print("{} is not valid".format(sys.argv[1]))


if __name__ == '__main__':
    main()
