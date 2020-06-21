import logging
import sys
from logging.handlers import TimedRotatingFileHandler

class MyLogger:

    FORMATTER = logging.Formatter("%(asctime)s %(filename)s %(funcName)s:%(lineno)d [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

    def __init__(self, logger_name, create_file=False, 
            logger_level="DEBUG", root="./"):
        self.ROOT = root
        self.logger_level = getattr(logging, logger_level)

        self.logger = logging.getLogger(logger_name)
        self.logger.setLevel(self.logger_level)
        self.logger.propagate = False

        self.add_handler()
        if create_file:
            self.add_handler(filename="all.log")

    def add_handler(self, level="NOTSET", filename=None):
        if filename == None:
            handler = logging.StreamHandler(sys.stdout)
        else:
            handler = TimedRotatingFileHandler(self.ROOT + filename, when='W0')
        handler.setFormatter(MyLogger.FORMATTER)
        handler.setLevel(level)
        self.logger.addHandler(handler)
        return 

    def set_logger_level(self, new_level):
        self.logger_level = getattr(logging, new_level)
        self.logger.setLevel(self.logger_level)
        return

    def retrieve_logger(self):
        return self.logger


# test use case:

# logObj = MyLogger("test", logger_level="DEBUG")
# mlog = logObj.retrieve_logger()
# mlog.debug("hei")
# mlog.info("hei")
# mlog.warning("hei")
# mlog.error("hei")
# mlog.critical("hei")
