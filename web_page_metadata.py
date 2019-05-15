import json

class WebPageMetadata(object):
    WEB_PAGE_METADATA_FILE_FORMAT = "{web_page_data_file}.metadata.json"

    URL_LINKS = "url_links"

    def __init__(self, url_links):
        self.url_links = url_links

    @classmethod
    def load_metadata_from_file(cls, web_page_metadata_file_path):
        with open(web_page_metadata_file_path, 'r') as f:
            metadata_dict = json.load(f)
        return WebPageMetadata(**metadata_dict)

    def write_metadata_to_file(self, web_page_metadata_file_path):
        metadata_dict = {self.URL_LINKS: list(self.url_links)}
        with open(web_page_metadata_file_path, 'w') as f:  # writing JSON object
            json.dump(metadata_dict, f)
