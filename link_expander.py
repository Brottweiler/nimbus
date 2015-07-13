#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import abc
import re

import requests
from bs4 import BeautifulSoup


class LinkExpander(object):
    """ returns expanded url previews from text containing oc.tc urls """
    def __init__(self, text):
        self.urls = self.get_urls(text)

    def get_urls(self, text):
        """ get urls from message text """
        m = 'oc.tc/'
        urls = filter(lambda x: m in x and not x.endswith('s/'), text.split())
        return [url.strip('<').strip('>') for url in urls]

    def process_urls(self):
        for url in self.urls:
            if 'forums' in url or 'topics' in url:
                yield ForumScraper(url).get_data()
            elif 'punishments' in url:
                yield PunishmentScraper(url).get_data()


class OCNScraper(object):
    """ oc.tc page scraper base class """
    __metaclass__ = abc.ABCMeta

    def __init__(self, url):
        self.url = url
        self.soup = None

    def make_soup(self):
        r = requests.get(self.url)
        if r.status_code != 200:
            print("Can't open url.")
            return
        return BeautifulSoup(r.content)

    @abc.abstractmethod
    def get_data(self):
        pass


class ForumScraper(OCNScraper):
    """ get data from forum topic to create an expanded link """

    def get_data(self):
        soup = self.make_soup()
        url = self.url
        post_id = url.split('#')[1] if '#' in url else None

        d = {}
        try:
            d['title_link'] = url
            d['title'] = soup.title.string.split('-')[0].strip()

            if post_id:
                post = soup.find('div', {'class': '', 'id': post_id})
            else:
                post = soup.find('div', id=re.compile(r'[0-9]+'))

            author = post.a['href'].strip('/')
            d['author_name'] = author
            d['author_link'] = 'https://www.oc.tc/' + author
            d['author_icon'] = post.img['src'].replace('32@2x.png', '16@2x.png')

            text = post.find('div', {'class': 'converted post-content'}).contents[1].find(text=True)
            d['text'] = self.decratain(text)

            d['fallback'] = '%s: %s' % (d['author_name'], self.decratain(text, 40))

        except (AttributeError, IndexError) as e:
            print("Can't read html: %s" % e)
            return

        return d

    def decratain(self, text, limit=70):
        """ trim unfurled message to a reasonable length (<3 crats ¯\_(ツ)_/¯) """
        if len(text) >= limit:
            return ' '.join(text.split()[:-1]) + ' ...'
        else:
            return text


class PunishmentScraper(OCNScraper):
    """ get data from punishment page to create an expanded link """

    def get_data(self):
        soup = self.make_soup()

        try:
            pun = soup.find('section', {'class': 'punishment'})

            # get values for 'active', 'automatic', 'expires', 'match' and 'server
            # which are all inside classless h3 tags
            bare_h3s = pun.find_all('h3', {'class': None})
            d = {h3.small.text: h3.contents[2].strip() for h3 in bare_h3s}

            d['punishee'] = pun.find('h1', {'class': 'punished'}).a.text
            d['punisher'] = pun.find('h3', {'class': 'punisher'}).a.text
            d['when'] = pun.find('small', {'rel': 'tooltip'})['title']
            d['reason'] = pun.find('h3', {'class': 'reason'}).contents[2].strip()
            d['pun_type'] = pun.find('h3', {'class': 'type'}).contents[2].strip()
        except (AttributeError, IndexError) as e:
            print("Can't read html: %s" % e)
            return

        return self.format_data(d)

    def format_data(self, d):
        """ generate slack message attachment """
        a = {}
        verb = 'punished' if d['pun_type'] == 'Ban' else 'warned'
        a['fallback'] = '%s %s by %s with reason "%s"' % \
                        (d['punishee'], verb, d['punisher'], d['reason'])

        a['text'] = a['fallback']
        return a

def expand_links(text, content, sc):
    """ expand links from oc.tc """
    le = LinkExpander(text)

    for a in le.process_urls():
        if a:
            content.update({'type': 'message', 'text': ' ', 'attachments': json.dumps([a])})
            sc.api_call('chat.postMessage', **content)
            print('Expanded url')
