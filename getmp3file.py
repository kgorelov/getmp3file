#!/usr/bin/env python

# This script is meant to download files from musicmp3.spb.ru
# file sharing service.
#
# Usage gettempfile.py 


import os
import sys
import urllib2
import optparse
import logging

import html5lib
from html5lib import treebuilders
from lxml.etree import ElementTree
from urlparse import urlparse, urlunparse

################################################################################

class MP3Parser:
    def __init__(self, url):
        self.url = url
        urlp = urlparse(url)
        self.baseurl = urlp.scheme + "://" + urlp.netloc;
    def parse(self):
        eparser = html5lib.HTMLParser(tree=treebuilders.getTreeBuilder("lxml", ElementTree))
        et = eparser.parse(urllib2.urlopen(self.url).read())
        album = et.xpath("//div[@id='MP3']/h2[2]")[0].text.encode("utf8")
        refs = et.xpath("//table[@class='video']/tbody/tr/td[1]/a")
        res = {}
        for r in refs:
            res[r.text] = self.baseurl + r.attrib['href'];
        return res

################################################################################

if __name__ == "__main__":
    mp3 = MP3Parser("http://musicmp3.spb.ru/album/41006/live_in_madrid.htm")
    mp3urls = mp3.parse()
    print mp3urls


