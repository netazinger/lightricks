import re
import os
import csv
import urllib2
import unicodedata
from time import time
import cachetools.func
from BeautifulSoup import BeautifulSoup
from collections import namedtuple, OrderedDict

from web_page_metadata import WebPageMetadata
from urlparse import urlparse
from url_status import UrlStatus
UrlResult = namedtuple("UrlResult", ["depth", "ratio", "status"])

class FailedProcessFile(Exception):
    UNKNOWN = -1
    EXTRACT_CHAILD_LINKS = -2
    def __init__(self, msg, error_code=UNKNOWN):
        self.msg = msg
        self.error_code = error_code

    def __str__(self):
        return "%s. Error code: %s" % (self.msg, self.error_code)

class WebCrawler(object):
    """ lightricks Crawler """

    ALLOWED_MIME_TYPE = {"text", "html"}
    DEFAULT_DIR_PATH = "/tmp/lightricks_Web_Crawler"
    WEB_PAGE_DATA_FILE_FORMAT = "{output_dir}/{url}"

    def __init__(self, url, depth=1, output_dir=None, us_cache=True):
        self.processed_url_to_url_status = OrderedDict()
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
    def extract_domain_from_url(cls, url):
        """
        extract the domain name  from a givven url
        :param url: a web page url
        :type url: str
        :return: the domain
        :rtype: str
        """
        return urlparse(url).netloc

    def should_process_url(self, url, depth):
        """
        check if url should bbe processed bad on the mime and the depth
        :param url: a web page url
        :type url: str
        :param depth: the depth of the url from the original url
        :type depth: int
        :return: where or not we should process this uurl
        :rtype: bool
        """
        if self.max_depth < depth or not url:
            return False

        file_mine = os.path.splitext(url)[-1].replace(".", "")
        if file_mine not in self.ALLOWED_MIME_TYPE:
            print "does not support file mime of type %s, we support %s" % (file_mine, self.ALLOWED_MIME_TYPE)
            return False
        return True


    @classmethod
    def simplify_url(cls, url):
        """
        convert the url to a file name that we can save on our fs
        this can be done much better
        :param url: a web page url
        :type url: str
        :return: a save able file name that origined from url
        :rtype: str
        """
        for pattren_to_remove in ["http://", "https://"]:
            url = url.replace(pattren_to_remove, "")
        return url.replace("/", "_")


    @classmethod
    def slugify(cls, value):
        """
        Normalizes string, converts to lowercase, removes non-alpha characters,
        and converts spaces to hyphens.
        """
        value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore')
        value = unicode(re.sub('[^\w\s-]', '', value).strip().lower())
        value = unicode(re.sub('[-\s]+', '-', value))
        return value


    @cachetools.func.lru_cache()
    def process_url(self, url):
        """
        process a url
        :param url: a web page url
        :type url: str
        :return: a tuple containing a list to all the url's child links abd the "same domain" ratio
        :rtype: tuple(list, float)
        """
        slugify_url = self.slugify(url)
        web_page_data_file_path = self.WEB_PAGE_DATA_FILE_FORMAT.format(output_dir=self.output_dir, url=slugify_url)
        web_page_metadata_file_path = WebPageMetadata.WEB_PAGE_METADATA_FILE_FORMAT.format(web_page_data_file=web_page_data_file_path)

        # check if url was processed in the past (based on file system)
        if self.us_cache and os.path.exists(web_page_data_file_path):
            if os.path.exists(web_page_metadata_file_path):
                web_page_metadata = WebPageMetadata.load_metadata_from_file(web_page_metadata_file_path)
                ratio = self.calc_ratio(url, web_page_metadata.url_links)
                return web_page_metadata.url_links, ratio
            else:
                web_page = open(web_page_data_file_path, "r").read()
        else:
            try:
                web_page = urllib2.urlopen(url)
            except urllib2.HTTPError as e:
                raise FailedProcessFile( "Filed to download %s" % url, e.code)

        # save page content locally
        open(web_page_data_file_path, "w").write(web_page.read())

        # read the page from the local file
        web_page = urllib2.urlopen("file://" + web_page_data_file_path)

        # process a page
        url_links = self.get_links_in_page(web_page)
        if url_links is None:
            os.remove(web_page_data_file_path)
            raise FailedProcessFile("failed extracting links", FailedProcessFile.EXTRACT_CHAILD_LINKS)
        WebPageMetadata(url_links).write_metadata_to_file(web_page_metadata_file_path)
        ratio = self.calc_ratio(url, url_links)
        return url_links, ratio

    def run(self):
        while self.urls_queue:
            url, depth = self.urls_queue.pop()

            if self.should_process_url(url, depth):
                continue

            print "processing %s with depth: %s" % (url, depth)
            url_status = UrlStatus(url, depth)
            url_links = []

            try:
                url_links, ratio = self.process_url(url)
                url_status.status = UrlStatus.SUCCESS
                url_status.ratio = ratio
            except FailedProcessFile as e:
                print str(e)
                url_status.error = e
                url_status.status = UrlStatus.FAILD
            self.processed_url_to_url_status[url] = url_status

            depth += 1

            # add all necessary "child" links to the queue
            if depth <= self.max_depth:
                for url_link in url_links:
                    if url_link not in self.processed_url_to_url_status:
                        self.urls_queue.append((url_link, depth))
                    else:
                        print "url %s was already processed" % url_link

        return self.build_output_report()

    def build_output_report(self):
        """
        build the out pu report of the program
        """
        output_file = "lightricks_Web_Crawler_%s.tsv" % time()
        with open(output_file, 'wt') as out_file:
            tsv_writer = csv.DictWriter(out_file, delimiter='\t', fieldnames=['url', 'depth', "ratio", "status", "error"])
            tsv_writer.writeheader()
            for url, url_status in self.processed_url_to_url_status.iteritems():
                tsv_writer.writerow(url_status.to_dict())
        return output_file

    @classmethod
    def get_links_in_page(cls, web_page):
        """
        get all child static links of a givven page
        :return: list of all the child links
        :rtype: list[str]
        """
        try:
            soup = BeautifulSoup(web_page)
            page_links = set()
            for link in soup.findAll('a', attrs={'href': re.compile("^http://")}):
                page_links.add(link.get('href'))
        except Exception as e:
            return None
        return page_links

    @classmethod
    def calc_ratio(cls, url, url_links):
        """
        get the "same domain" ratio of the url links
        :param url: a web page url
        :type url: str
        :param url_links: list of all the child links
        :type url_links: list[str]
        :return: "same domain" ratio
        :rtype: float
        """
        orig_domain = cls.extract_domain_from_url(url)

        if url_links:
            return len({domain_link for domain_link in url_links
                        if cls.extract_domain_from_url(domain_link) == orig_domain}) / float(len(url_links))
        else:
            return 0
