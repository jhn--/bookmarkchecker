#!/usr/bin/env python3

import argparse
import asyncio
import sys
from datetime import date, datetime
from os import path
from time import localtime, strftime
from collections import Counter
import matplotlib.pyplot as plt
import json
from numpy import arange

import aiohttp
from bs4 import BeautifulSoup


CONSENT = {'y', '', 'yes'}
CHOICES = {i for i in range(4)}


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
        return 0

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
        return 0

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

    @property
    def getRespCodeStats(self):
        """
        using collections.Counter to get the list of resp_codes and returning them
        # todo - present the data in prettier way
        """
        self.c = Counter([value['resp_code'] for value in self.details.values()])
        # print(self.c)
        response_codes = [rc for rc in self.c.keys()]
        num_of_sites = [numofsites for numofsites in self.c.values()]

        ## pie chart
        fig1, ax1 = plt.subplots()
        ax1.pie(num_of_sites, labels = response_codes)
        ax1.axis('equal')
        plt.show()

        #bar graph
        # plt.rcdefaults()
        # fig, ax = plt.subplots()

        # y_pos = arange(len(response_codes))
        
        # ax.barh(response_codes, width=num_of_sites, height=1, align='center')
        # ax.set_yticks(y_pos)
        # ax.set_yticklabels(response_codes)
        # ax.invert_yaxis()
        # ax.set_xlabel('Number of websites')

        # plt.show()
        return 0

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

        w = 20
        h = 20
        d = 70
        plt.figure(figsize=(w, h), dpi=d)
        plt.xlabel("Year")
        plt.ylabel("Bookmarks added")
        years = [year for year in self.bookmarkstats.keys()]
        num_of_bookmarks = [bookmarkcount[1][0] for bookmarkcount in self.bookmarkstats.items()]

        plt.plot(years, num_of_bookmarks)
        for x, y in zip(years, num_of_bookmarks):
            plt.text(x, y, f"{y}")
        plt.show()
        # return self.bookmarkstats
        # return [(kv[0], kv[1][0]) for kv in self.bookmarkstats.items()]
        return 0
    
    def exportJSON(self, output):
        with open(output, 'w') as jsonfp:
            json.dump(self.details, jsonfp)
        return 0

    def exportDetails(self):
        print("aloha")
        output = input("Please enter a destination filename (ie. /home/user/out.json): ")
        if path.exists(output):
            overwrite = input("File exists, overwrite? [Y/n]: ")
            if self.overwrite.lower() in CONSENT:
                self.exportJSON(output)
                print(f'File {output} has been updated.')
                return 0
            else:
                print('Exiting....')
                return 1
        else:
            self.exportJSON(output)
            print(f'File {output} has been created.')
            return 0


def convertEpochtoLocaltime(epoch):
    """
    convert epoch time to local time
    """
    return strftime('%Y-%m-%d %H:%M:%S %z', localtime(epoch))


def main(args):
    if (args.bookmark and args.json) or (not args.bookmark and not args.json):
        print("""
            Please load EITHER -
            1) An exported html file from Chrome
            or
            2) A json file exported from this program
            """)
        return 1
    elif (args.bookmark and not args.json):
        # print(f'{args}')
        bmc = bookmarkChecker(args.bookmark)
        print("Bookmark is being verified....")
        if bmc.populateDetails() == 0:
            print("Bookmark has been successfully verified, checking links....")
            asyncio.get_event_loop().run_until_complete(bmc.checkLinks())
            choice = None
            while choice not in CHOICES:
                choice = input("""
                    Bookmark links have been checked.
                    Select any of the following: 
                    1) Export bookmarks to a json file.
                    2) View the graph of the number of bookmarks added per year.
                    3) View the number of response codes.
                    0) Exit the program.
                    >>> 
                    """)
                if choice == '1':
                    bmc.exportDetails()
                elif choice == '2':
                    bmc.getBookmarkStats
                elif choice == '3':
                    print(bmc.getRespCodeStats)
                elif choice == '0':
                    print('Exiting....')
                    return 0
        else:
            print("Exported html file is unusable.")
            return 1
    elif (not args.bookmark and args.json):
        print(f'{args}')
    else:
        print(f'{args}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Bookmark checker for chrome bookmarks.")
    parser.add_argument("-b", "--bookmark", action="store", help="Load exported bookmark html file.")
    parser.add_argument("-j", "--json", action="store", help="Load json file.")
    args = parser.parse_args()
    main(args)