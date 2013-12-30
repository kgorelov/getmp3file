#!/usr/bin/env python
# -*- coding: utf-8 -*-

# This script is meant to download files from musicmp3.spb.ru
# file sharing service.
#
# Usage gettempfile.py URL


import os
import os.path
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
        self.parser = html5lib.HTMLParser(
            tree=treebuilders.getTreeBuilder("lxml", ElementTree))

    def parse(self):
        reader = urllib2.urlopen(self.url)
        page = reader.read()
        page = page.replace('xml:lang="ru"', '')
        et = self.parser.parse(page)
        return et

################################################################################

def get_first_element(et, xpath):
    try:
        et.xpath(xpath, namespaces={'xhtml':'http://www.w3.org/1999/xhtml'})[0].text.encode("utf8").strip()
    except IndexError:
        return None

class MP3SongsParser(MP3Parser):
    def parse_songs(self):
        # Parse the page
        et = self.parse()
        # Extract album year
        year = get_first_element(et, "//xhtml:div[@class='Name']/xhtml:i") or ""
        if len(year):
            year += " - "
        # Extract the artist name
        self.artist = et.xpath("//xhtml:div[@id='cntMain']/xhtml:div[@id='cntCenter']/xhtml:h1/xhtml:a", namespaces={'xhtml':'http://www.w3.org/1999/xhtml'})[0].text.encode("utf8").strip()
        if not self.artist:
            self.artist = 'Unknown'
        else:
            self.artist = self.artist.replace(' mp3','')
        # Get the album name
        self.album = year + et.xpath("//xhtml:div[@class='Name']", namespaces={'xhtml':'http://www.w3.org/1999/xhtml'})[0].text.encode("utf8").strip()
        info("Artist: %s" % self.artist)
        info("Album: %s" % self.album)
        # Extract song references
        refs = et.xpath("//xhtml:div[@class='albSong']/xhtml:div/xhtml:a[1]", namespaces={'xhtml':'http://www.w3.org/1999/xhtml'})
        self.songs = []
        for r in refs:
            self.songs.append((r.text,self.baseurl + r.attrib['href']))
            info("Found song: %s" % r.text)
            #debug("Song url: %s" % self.baseurl + r.attrib['href'])

    def get_album(self):
        return self.album

    def get_artist(self):
        return self.artist

    def get_songs(self):
        return self.songs

################################################################################

class MP3AlbumsParser(MP3Parser):
    def parse_songs(self):
        et = self.parse()

        refs = et.xpath("//xhtml:table[@class='video']/xhtml:tbody/xhtml:tr/xhtml:td[1]/xhtml:a", namespaces={'xhtml':'http://www.w3.org/1999/xhtml'})
        self.songs = {}
        for r in refs:
            self.songs[r.text] = self.baseurl + r.attrib['href'];
            info("Found album: %s" % r.text)

    def get_albums(self):
        return self.albums

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
        form = et.xpath("//xhtml:form[starts-with(@action,'/file')]", namespaces={'xhtml':'http://www.w3.org/1999/xhtml'})[0]
        self.action = form.attrib['action']
        self.robot_code = form.xpath("//xhtml:input[@name='robot_code']", namespaces={'xhtml':'http://www.w3.org/1999/xhtml'})[0].attrib['value']

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
        url = doc.xpath("//xhtml:div[@id='cntMain']//xhtml:center//xhtml:a", namespaces={'xhtml':'http://www.w3.org/1999/xhtml'})[0].text
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
        usage = "usage: %prog [options] URI"
        parser = optparse.OptionParser(usage=usage)

        parser.add_option('-D', '--dry',
                          dest = 'dry',
                          action = 'store_true',
                          help = 'Dry run. Do not download files, only traverse through pages')

        parser.add_option('-f', '--filenames',
                          dest = 'filenames',
                          action = 'store_true',
                          help = 'Store downloaded files under names parsed from the webpage')

        parser.add_option('-m', '--mediadir',
                          dest = 'mediadir',
                          type = 'string',
                          default = '~/Music',
                          help = 'Path to your media library')

        parser.add_option('-n', '--naming',
                          dest = 'naming',
                          type = 'string',
                          default = 'full',
                          help = 'Destination directory naming scheme: full (artist/album/song), album, song')

        (self.options, self.arguments) = parser.parse_args()

        if len(self.arguments) != 1:
            parser.print_help();
            sys.exit(1);

        # Start url
        self.url = self.arguments[0]
        self.dest = os.path.realpath(
            os.path.expanduser(self.options.mediadir))

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

    def download_albums(self, url):
        debug("XXX Implement me")

    def download_songs(self, url):
        mp3 = MP3SongsParser(self.url)
        mp3.parse_songs()
        # Create album directory under dest
        if self.options.naming == 'full':
            self.album_dir = os.path.join(self.dest, mp3.get_artist(), mp3.get_album())
        elif self.options.naming == 'album':
            self.album_dir = os.path.join(self.dest, mp3.get_album())
        elif self.options.naming == 'song':
            self.album_dir = self.dest
        else:
            raise Exception("Unknown naming scheme: %s" % self.options.naming)

        debug("Album directory: %s", self.album_dir)

        if self.options.dry:
            return
        
        self.make_dir(self.album_dir)

        songs = mp3.get_songs()
        for song in songs:
            tmpfp = TMPFileParser(song[1])
            tmpfp.parse()

            filename = None
            if self.options.filenames:
                filename =  song[0] + ".mp3"
            
            tmpfp.download(self.album_dir, filename)

    def run(self):
        info("Dowloading %s" % self.url)
        # XXX 2DO: Match the url against a regexp,
        # call down_songs or down_albums
        # Make sure to use command line options to override defaults
        self.download_songs(self.url)
        return 0


################################################################################

if __name__ == "__main__":
    main = Main()
    sys.exit(main.run())


