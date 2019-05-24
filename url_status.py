class UrlStatus(object):
    STARTED = "started"
    SUCCESS = "success"
    FAILD = "faild"
    
    def __init__(self, url, depth, ratio=None, status=STARTED, error=None):
        self.url = url
        self.depth = depth
        ratio=None
        self.status = status
        self.error = error
        
    def to_dict(self):
        return self.__dict__
        
        