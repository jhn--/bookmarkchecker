#!/usr/bin/env python3


from os import path
import sys
import re
# import click


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
        '''
        for i in matches:
            print(i)
        '''
        for match in matches:
            self.bookmark_repo[match] = []

        # for key, value in self.bookmark_repo.items():
        #     print("{}, {}".format(key, value))

    def __repr__(self):
        for key, value in self.bookmark_repo.items():
            print(f"{key}, {value}")

        # return self.bookmark_repo


# bookmark = bookmarkchecker()

# @click.command()
# @click.option('--help', )


def main():
    if len(sys.argv) != 2:
        print("blah")
        exit()
    if path.exists(sys.argv[1]):
        bookmark = bookmarkchecker(sys.argv[1])
        bookmark.openbookmark()
        bookmark.getbookmarklinks()
        print(bookmark)
    else:
        print("Path is not valid.")


if __name__ == '__main__':
    main()
