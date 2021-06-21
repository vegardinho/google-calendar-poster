import logging
from logging import Formatter
import sys
from copy import copy
from logging.handlers import TimedRotatingFileHandler

class ColoredFormatter(Formatter):

    MAPPING = {
        'DEBUG'   : 37, # white
        'INFO'    : 36, # cyan
        'WARNING' : 33, # yellow
        'ERROR'   : 31, # red
        'CRITICAL': "1;31", # bold red
    }

    PREFIX = '\033['
    SUFFIX = '\033[0m'

    def __init__(self, pattern, date_fmt):
        Formatter.__init__(self, pattern, datefmt=date_fmt)

    def format(self, record):
        colored_record = copy(record)
        levelname = colored_record.levelname
        seq = ColoredFormatter.MAPPING.get(levelname, 37) # default white
        colored_levelname = ('{0}{1}m{2}{3}') \
            .format(ColoredFormatter.PREFIX, seq, levelname, ColoredFormatter.SUFFIX)
        colored_record.levelname = colored_levelname
        return Formatter.format(self, colored_record)


class MyLogger:

    FORMAT = "%(asctime)s %(filename)s [%(levelname)s] %(funcName)s:%(lineno)d %(message)s"
    DATE_FMT = "%Y-%m-%d %H:%M:%S"
    FORMATTER = ColoredFormatter(FORMAT, DATE_FMT)

    # Creates a logger, adds handler for printing to screen, 
    # plus optional written copy to file "all.log"
    def __init__(self, logger_name, cre_f_ha=False, cre_sys_h=True, 
            logger_level="DEBUG", root="./", o_write_all=False, 
            overwrite=False, f_ha="DEBUG", sys_ha="DEBUG"):
        self.ROOT = root
        self.logger_level = getattr(logging, logger_level)
        self.o_write_all = o_write_all

        self.logger = logging.getLogger(logger_name)
        self.logger.setLevel(self.logger_level)
        self.logger.propagate = False

        if cre_sys_h:
            self.add_handler(level=sys_ha) 
        if cre_f_ha:
            self.add_handler(overwrite=overwrite, level=f_ha, filename="all.log")

    # Add handlers, for either writing to file or screen
    def add_handler(self, level="NOTSET", filename=None, 
            overwrite=False):
        if filename == None:
            handler = logging.StreamHandler(sys.stdout)
        elif overwrite or self.o_write_all:
            handler = logging.FileHandler(mode="w", filename=self.ROOT + filename)
        else:
            handler = TimedRotatingFileHandler(self.ROOT + filename, 
                when='W0')
        handler.setFormatter(MyLogger.FORMATTER)
        handler.setLevel(level)
        self.logger.addHandler(handler)
        return 

    # Set level on logger-level (may affect handler-level output)
    def set_logger_level(self, new_level):
        self.logger_level = getattr(logging, new_level)
        self.logger.setLevel(self.logger_level)
        return

    def retrieve_logger(self):
        return self.logger


# test use case:
#
# logObj = MyLogger("test", logger_level="WARNING")
# mlog = logObj.retrieve_logger()
# mlog.debug("hei")
# mlog.info("hei")
# mlog.warning("hei")
# mlog.error("hei")
# mlog.critical("hei")
