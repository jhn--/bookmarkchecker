#!/usr/bin/env python3


from os import path
import sys
import re
# import click
from pprint import pprint


class bookmark(object):
    """docstring for bookmark."""

    def __init__(self, name, isonline=False):
        self.name = name
        self.isonline = isonline

    def __repr__(self):
        # print("{}, {}".format(self.name, self.isonline))
        return f"{self.name}, {self.isonline}"


class bookmarkchecker(object):
    """docstring for bookmarkchecker."""

    def __init__(self, bookmark_path):
        self.bookmark_path = bookmark_path
        self.bookmark_repo = {}
        self.bookmark_contents = ''

    def openbookmark(self):
        # print("a")
        with open(self.bookmark_path, 'r') as fp:
            self.bookmark_contents = fp.read()
        fp.close()
        # print(self.bookmark_contents)
        return self.bookmark_contents

    def getbookmarklinks(self):
        # regex = r"(https?:\/\/|\b(?:[a-z\d]+\.)(?:(?:[^\s()<>]+|\((?:[^\s()<>]+|(?:\([^\s()<>]+\)))?\))+(?:\((?:[^\s()<>]+|(?:\(?:[^\s()<>]+\)))?\)|[^\s`!()\[\]{};:'.,<>?«»“”‘’]))?"

        regex = "(?<=A HREF=\")(.*)(?=\" ADD_DATE)"
        matches = re.findall(regex, self.bookmark_contents, re.MULTILINE | re.IGNORECASE)

        id = 0

        for match in matches:
            print("{}, {}".format(id, match))
            self.bookmark_repo[id] = bookmark(match)
            id += 1

    def __repr__(self):
        pprint(self.bookmark_repo)
        # return self.bookmark_repo
        # print(self.bookmark_repo[id])

        # for id, bm in self.bookmark_repo.items():
        #     print("{}, {}", format(id, bm))

        # for key, value in self.bookmark_repo.items():
        #     print(f"{key}, {value}")

        # return self.bookmark_repo


# @click.command()
# @click.option('--help', )


def main():
    if len(sys.argv) != 2:
        print("blah")
        exit()
    if path.exists(sys.argv[1]):
        bm_checker = bookmarkchecker(sys.argv[1])
        bm_checker.openbookmark()
        bm_checker.getbookmarklinks()
        # print(bm_checker)
    else:
        print("Path is not valid.")


if __name__ == '__main__':
    main()
