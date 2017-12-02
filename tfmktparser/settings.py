import urllib2
import logging
import re
from retrying import retry

LOCAL = 0
REMOTE = 1
HOST = "https://www.transfermarkt.co.uk"
HOME_RAW = "C:\\Users\\david\\git\\tfmkt-parser\\"
#HOME_RAW = "D:\\git-playground\\tfmkt-parser\\tfmkt-parser\\"

"""
Helper function. Downloads from URL with retries
"""
@retry(stop_max_attempt_number=3)
def safe_url_getter(uri):
    logger = logging.getLogger(__name__)
    if re.match(r"file://.*", uri):
        path = uri[8::]
        logger.debug("Retrieve from local filesystem {}".format(path))
        try:
            with open(path, 'r') as f:
                content = f.read()
                f.close()
                return content
        except:
            logger.error("Error reading local file {}".format(uri))
            return None
    else:
        try:
            req = urllib2.Request(uri, headers={'User-Agent': 'Mozilla/5.0'})
            file = urllib2.urlopen(req)
        except urllib2.HTTPError as err:
            logger.warn("Attempt to download file {} failed: {}".format(uri), err.read())
            return None
        except urllib2.URLError:
            logger.warn("Attempt to get file {} failed: {}".format(uri, urllib2.URLError))
            return None
        else:
            return file.read()
