#!/usr/bin/env python

# This script is meant to download files from musicmp3.spb.ru
# file sharing service.
#
# Usage gettempfile.py 


import os
import re
import sys
import urllib
import urllib2
import optparse
import logging
from logging import debug, info, warn, error

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
        self.album = et.xpath("//div[@id='MP3']//h2[last()]")[-1].text.encode("utf8")
        info("Album name: %s" % self.album)
        refs = et.xpath("//table[@class='video']/tbody/tr/td[1]/a")
        self.songs = {}
        for r in refs:
            self.songs[r.text] = self.baseurl + r.attrib['href'];
            info("Found song: %s" % r.text)

    def get_album(self):
        return self.album

    def get_songs(self):
        return self.songs

################################################################################

class TMPFileParser:
    def __init__(self, url):
        self.url = url

    def parse(self):
        eparser = html5lib.HTMLParser(tree=treebuilders.getTreeBuilder("lxml", ElementTree))
        #debug("Downloading: '%s'" % self.url)
        reader = urllib2.urlopen(self.url)
        page = reader.read()
        self.url = reader.geturl()
        urlp = urlparse(self.url)
        self.baseurl = urlp.scheme + "://" + urlp.netloc
        page = page.replace('xml:lang="ru"', '')
        et = eparser.parse(page)
        form = et.xpath("//form[starts-with(@action,'/file')]")[0]
        self.action = form.attrib['action']
        self.robot_code = form.xpath("//input[@name='robot_code']")[0].attrib['value']

    def download(self, directory, filename = None):
        url = self.baseurl + self.action
        info("Downloading from tmpfile: %s" % url)
        debug("robot code: %s" % self.robot_code)
        values = {'robot_code': self.robot_code}
        data = urllib.urlencode(values)
        req = urllib2.Request(url, data)
        response = urllib2.urlopen(req)

        page = response.read()
        page = page.replace('xml:lang="ru"', '') 
        eparser = html5lib.HTMLParser(tree=treebuilders.getTreeBuilder("lxml", ElementTree))
        doc = eparser.parse(page)
        url = doc.xpath("//div[@id='cntMain']//center//a")[0].text
        response = urllib2.urlopen(url)

        inf = response.info()
        if filename is None:
            match = re.search('filename="(.*)"', inf['Content-Disposition'])
            filename = match.group(1)

        debug("Destination directory: %s" % directory)
        debug("Destination file: %s" % filename)
        self.save(response, directory + '/' + filename)

    def save(self, fd_in, filename):
        try:
            fd_out = open(filename, 'w')
            fd_out.write(fd_in.read())
        except IOError, e:
            error("Error saving file %s: %s" (filename, repr(e)))

################################################################################

class Main:
    def __init__(self):
        usage = "usage: %prog [options] URI DESTDIR"
        parser = optparse.OptionParser(usage=usage)

        parser.add_option('-D', '--dry',
                          dest = 'dry',
                          action = 'store_true',
                          help = 'Dry run. Do not download files, only traverse through pages')

        parser.add_option('-f', '--filenames',
                          dest = 'filenames',
                          action = 'store_true',
                          help = 'Store downloaded files under names parsed from the webpage')

        (self.options, self.arguments) = parser.parse_args()

        if len(self.arguments) != 2:
            parser.print_help();
            sys.exit(1);

        # Start url
        self.url = self.arguments[0]
        self.dest = self.arguments[1]

        # Set unbuffered stdout
        sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', 0)
        # Set up logging
        self.log_setup()

    def log_setup(self):
        #logging.getLogger().setLevel(logging.INFO)
        logging.getLogger().setLevel(logging.DEBUG)
        ch = logging.StreamHandler()
        #ch.setLevel(logging.INFO)
        ch.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            "[%(asctime)s] (%(levelname)s) %(message)s",
            "%Y-%m-%d %H:%M:%S")
        ch.setFormatter(formatter)
        logger = logging.getLogger()
        logger.addHandler(ch)

    def make_dir(self, f):
        if not os.path.isdir(f):
            debug("Creating album directory: %s", f)
            os.makedirs(f)

    def run(self):
        info("Dowloading %s" % self.url)
        mp3 = MP3Parser(self.url)
        mp3.parse()
        # Create album directory under dest
        self.album_dir = self.dest + "/" + mp3.get_album()
        debug("Album directory: %s", self.album_dir)
        self.make_dir(self.album_dir)

        songs = mp3.get_songs()
        for song in songs:
            tmpfp = TMPFileParser(songs[song])
            tmpfp.parse()

            filename = None
            if self.options.filenames:
                filename =  song + ".mp3"
            
            tmpfp.download(self.album_dir, filename)
        return 0


################################################################################

if __name__ == "__main__":
    main = Main()
    sys.exit(main.run())


