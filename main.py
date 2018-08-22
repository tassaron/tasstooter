#!/usr/bin/env python3
"""
tasstooter, a simple program for organizing toots & tooting them later
"""
from mastodon import Mastodon
import configparser
import os
import random
import argparse
from string import ascii_letters


class TootArchive(configparser.ConfigParser):
    def __init__(self):
        super().__init__(interpolation=None)
        self.optionxform = str

        def makeConfigPath():
            dotConfigPath = os.getenv("XDG_CONFIG_HOME")
            if dotConfigPath:
                configPath = os.path.join(
                    dotConfigPath, 'tasstooter'
                )
            else:
                # use fallback path which XDG_CONFIG_HOME is normally set to
                configPath = os.path.join(
                    os.getenv("HOME"), '.config', 'tasstooter'
                )
            if not os.path.exists(configPath):
                os.makedirs(configPath)
            return configPath

        # load archive or make a new empty text file if none exists
        configPath = makeConfigPath()
        self.path = os.path.join(configPath, "tootarchive.ini")
        if not os.path.exists(self.path):
            with open(self.path, 'w') as f:
                f.write('[DEFAULT]\nused = 0\nsource = 0\n\n[LASTTOOT]')
        self.read(self.path)

    def save(self):
        with open(self.path, 'w') as f:
            self.write(f)

    def add(self, toot, source=None):
        # create a new section in the ini file
        while True:
            pname = "".join([random.choice(ascii_letters) for i in range(12)])
            if pname not in self.sections():
                self.add_section(pname)
                break

        self[pname]['toot'] = toot
        if source and source != '0':
            self[pname]['source'] = source
        self.save()

    def fetch(self):
        i = 0
        while i < len(self.sections()) + 1:
            i += 1
            section = random.choice(self.sections())
            if section == 'LASTTOOT':
                continue
            newToot = self[section]
            if newToot['used'] == "0" and (
                        newToot['source'] != self['LASTTOOT']['source']
                    ):
                newToot['used'] = "1"
                self['LASTTOOT']['source'] = newToot['source']
                self.save()
                return newToot
        return None


def login():
    mastodon = Mastodon(
        client_id='tasstooter_clientcred.secret',
        api_base_url='https://botsin.space'
    )
    mastodon.log_in(
        'email,
        'password',
        to_file='tasstooter_usercred.secret'
    )


def connect():
    # Create actual API instance
    mastodon = Mastodon(
        access_token='tasstooter_usercred.secret',
        api_base_url='https://botsin.space'
    )
    return mastodon


def main():
    parser = argparse.ArgumentParser(
        description='organize toots and toot them later'
    )
    parser.add_argument(
        '-l', '--login',
        help='log in (necessary before you can toot)',
        action='store_true'
    )
    parser.add_argument(
        '-i', '--insert',
        metavar=('FILENAME',),
        help='insert a newline-separated file of sourceless toots into archive'
    )
    parser.add_argument(
        '-a', '--add',
        help='add toot to archive with a source url (0 for no source)',
        nargs=2,
        metavar=('TOOT', 'SOURCE')
    )
    parser.add_argument(
        '-t', '--toot',
        help='toot a toot from archive with different source than last toot',
        action='store_true'
    )
    arg = parser.parse_args()

    if arg.login:
        login()

    if arg.add or arg.toot or arg.insert:
        archive = TootArchive()

    if arg.insert:
        with open(arg.insert, 'r') as f:
            i = 0
            for line in f:
                archive.add(line.strip())
                i += 1
        print('Inserted %s toots into the archive' % str(i))

    if arg.add:
        archive.add(arg.add[0], arg.add[1])

    if arg.toot:
        newToot = archive.fetch()
        if newToot:
            mastodon = connect()
            print('tooting: %s' % newToot['toot'])
            mastodon.toot(newToot['toot'])
        else:
            print('No toots in the archive')


if __name__ == "__main__":
    """
    Mastodon.create_app(
         'tasstooter',
         api_base_url = 'https://botsin.space',
         to_file = 'tasstooter_clientcred.secret'
    )
    """
    main()
