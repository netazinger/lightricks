import re
import os
import csv
import urllib2
import datetime
import cachetools.func
from BeautifulSoup import BeautifulSoup
from collections import namedtuple, OrderedDict

from web_page_metadata import WebPageMetadata
from urlparse import urlparse
UrlResult = namedtuple("UrlResult", ["depth", "ratio"])

class WebCrawler(object):
    ALLOWED_MIME_TYPE = {"text", "html"}
    DEFAULT_DIR_PATH = "/tmp/lightricks_Web_Crawler"
    WEB_PAGE_DATA_FILE_FORMAT = "{output_dir}/{url}"

    def __init__(self, url, depth=1, output_dir=None, us_cache=True):
        self.processed_url_to_url_result = OrderedDict()
        self.max_depth = depth
        self.urls_queue = [(url, 1)]
        self.output_dir = output_dir or self.DEFAULT_DIR_PATH
        self.us_cache = us_cache
        if not os.path.isdir(self.output_dir):
            if os.path.exists(self.output_dir):
                raise RuntimeError("outpath %s is not a directory" % self.output_dir)
            os.mkdir(self.output_dir)


    @classmethod
    @cachetools.func.lru_cache()
    def extract_domin_from_url(cls, url):
        return urlparse(url).netloc

    def should_process_url(self, url, depth):
        if self.max_depth < depth:
            return False

        file_mine = os.path.splitext(url)[0].replace(".", "")
        if file_mine not in self.ALLOWED_MIME_TYPE:
            print "does not support file mime of type %s, we support %s" % (file_mine, self.ALLOWED_MIME_TYPE)
            return False
        return True


    @classmethod
    def simplify_url(cls, url):
        for pattren_to_remove in ["http://", "https://"]:
            url = url.replace(pattren_to_remove, "")
        return url.replace("/", "_")

    @cachetools.func.lru_cache()
    def process_url(self, url):
        simplify_url = self.simplify_url(url)
        web_page_data_file_path = self.WEB_PAGE_DATA_FILE_FORMAT.format(output_dir=self.output_dir, url=simplify_url)
        web_page_metadata_file_path = WebPageMetadata.WEB_PAGE_METADATA_FILE_FORMAT.format(web_page_data_file=web_page_data_file_path)

        # check if url was processed in the past (based on file system)
        if self.us_cache and os.path.exists(web_page_data_file_path):
            if os.path.exists(web_page_metadata_file_path):
                web_page_metadata = WebPageMetadata.load_metadata_from_file(web_page_metadata_file_path)
                ratio = self.calc_ratio(url, web_page_metadata.url_links)
                return web_page_metadata.url_links, ratio
            else:

                html_page = open(web_page_data_file_path, "r").read()
        else:
            html_page = urllib2.urlopen(url)

        # save page content locally
        open(web_page_data_file_path, "w").write(html_page.read())

        # read the page from the local file
        html_page = urllib2.urlopen("file://" + web_page_data_file_path)

        # process a page
        url_links = self.get_links_in_page(html_page)
        WebPageMetadata(url_links).write_metadata_to_file(web_page_metadata_file_path)
        ratio = self.calc_ratio(url, url_links)
        return url_links, ratio

    def run(self):
        while self.urls_queue:
            url, depth = self.urls_queue.pop()

            if self.should_process_url(url, depth):
                continue

            print "processing %s with depth: %s" % (url, depth)

            url_links, ratio = self.process_url(url)
            self.processed_url_to_url_result[url] = UrlResult(depth=depth, ratio=ratio)

            depth += 1
            if depth <= self.max_depth:
                for url_link in url_links:
                    if url_link not in self.processed_url_to_url_result:
                        self.urls_queue.append((url_link, depth))
                    else:
                        print "url %s was already processed" % url_link

        self.build_output_report()

    def build_output_report(self):
        with open("lightricks_Web_Crawler_%s.tsv" % datetime.datetime.now(), 'wt') as out_file:
            tsv_writer = csv.writer(out_file, delimiter='\t')
            tsv_writer.writerow(['url', 'depth', "ratio"])
            for url, url_result in self.processed_url_to_url_result.iteritems():
                tsv_writer.writerow([url, url_result.depth, url_result.ratio])

    @classmethod
    def get_links_in_page(cls, html_page):
        soup = BeautifulSoup(html_page)
        page_links = set()
        for link in soup.findAll('a', attrs={'href': re.compile("^http://")}):
            page_links.add(link.get('href'))
        return page_links

    @classmethod
    def calc_ratio(cls, url, url_links):
        orig_domain = cls.extract_domin_from_url(url)

        return len({domain_link for domain_link in url_links
                    if cls.extract_domin_from_url(domain_link) == orig_domain}) / float(len(url_links))
