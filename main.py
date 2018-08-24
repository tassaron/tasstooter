#!/usr/bin/env python3
"""
tasstooter, a simple program for organizing toots & tooting them later
"""
from mastodon import Mastodon, StreamListener
import configparser
import os
import random
import argparse
from string import ascii_letters


class SavableConfigParser(configparser.ConfigParser):
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

        self.configPath = makeConfigPath()

    def save(self):
        with open(self.path, 'w') as f:
            self.write(f)


class SourceArchive(SavableConfigParser):
    def __init__(self):
        super().__init__()

        # load archive or make a new empty text file if none exists
        self.path = os.path.join(self.configPath, "sourcearchive.ini")
        if not os.path.exists(self.path):
            with open(self.path, 'w') as f:
                f.write('[DEFAULT]\nused = 0')
        self.read(self.path)

    def add(self, tootId, source):
        tootId = str(tootId)
        self.add_section(tootId)
        self[tootId]['source'] = source
        self.save()


class TootArchive(SavableConfigParser):
    def __init__(self):
        super().__init__()

        # load archive or make a new empty text file if none exists
        self.path = os.path.join(self.configPath, "tootarchive.ini")
        if not os.path.exists(self.path):
            with open(self.path, 'w') as f:
                f.write('[DEFAULT]\nused = 0\nsource = 0\n\n[LASTTOOT]')
        self.read(self.path)

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


class ReplyBot(StreamListener):
    def __init__(self, mastodon, srcArchive):
        super().__init__()
        self.mastodon = mastodon
        self.archive = srcArchive

    def on_notification(self, notification):
        acct = notification.get("account").get("acct")
        notif_type = notification.get("type")
        if notif_type == "reblog":
            print("boosted by %s" % acct)
            return
        elif notif_type == "favourite":
            print("favourited by %s" % acct)
            return
        elif notif_type == "follow":
            print("new follower: %s" % acct)
            return
        elif notif_type != "mention":
            print("unknown notification.")
            return

        status = notification.get("status")
        if status is None:
            print("status was none.")
            return
        content = cleanup(status.get("content"))
        if content is None:
            print("content was none.")
            return
        elif "source" not in content:
            print("reply from %s: %s" % (acct, content))
            return

        # finally, toot the source if we can!
        target = status.get("in_reply_to_id")
        try:
            if self.archive[str(target)]['used'] == '0':
                url = self.archive[str(target)]['source']
                self.mastodon.status_post(
                    "@%s %s" % (acct, url), in_reply_to_id=status
                )
                self.archive[str(target)]['used'] = '1'
                self.archive.save()
        except KeyError:
            print("reply to an id not found in archive: %s" % str(target))
            return


def cleanup(content):
    if content is None:
        return None
    # there must be a better way to de-HTML this string...
    content = content.replace("<p>", "").replace("</p>", "")
    content = content.replace("&apos;", "'").split()
    content = (
        ' '.join(
            [word.lower() for word in content if
                set(word).isdisjoint(set("@<>\""))]
        )
    )
    return content


def login():
    mastodon = Mastodon(
        client_id='tasstooter_clientcred.secret',
        api_base_url='https://botsin.space'
    )
    mastodon.log_in(
        'email',
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
    parser.add_argument(
        '-r', '--reply',
        help='enter reply mode to respond to requests for source url',
        action='store_true'
    )
    arg = parser.parse_args()

    if arg.login:
        login()

    if arg.add or arg.toot or arg.insert or arg.reply:
        archive = TootArchive()
        srcArchive = SourceArchive()

    if arg.insert:
        with open(arg.insert, 'r') as f:
            i = 0
            for line in f:
                archive.add(line.strip())
                i += 1
        print('Inserted %s toots into the archive' % str(i))

    if arg.add:
        archive.add(arg.add[0], arg.add[1])

    # now things that require connecting to an instance
    mastodon = None
    if arg.toot:
        newToot = archive.fetch()
        if newToot:
            mastodon = connect()
            print('tooting: %s' % newToot['toot'])
            t = mastodon.toot(newToot['toot'])
            newTootId = t.get("id")
            srcArchive.add(newTootId, newToot['source'])
        else:
            print('No toots in the archive')

    if arg.reply:
        if mastodon is None:
            mastodon = connect()
        print("now in reply mode! press ctrl+c to stop")
        try:
            bot = ReplyBot(mastodon, srcArchive)
            mastodon.stream_user(listener=bot)
        except KeyboardInterrupt:
            print("interrupt received, signing off...")


if __name__ == "__main__":
    """
    Mastodon.create_app(
         'tasstooter',
         api_base_url = 'https://botsin.space',
         to_file = 'tasstooter_clientcred.secret'
    )
    """
    main()
