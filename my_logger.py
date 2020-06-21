import logging
import sys
from logging.handlers import TimedRotatingFileHandler

class MyLogger:

    FORMATTER = logging.Formatter("%(asctime)s %(filename)s %(funcName)s:%(lineno)d [%(levelname)s] %(message)s", 
        datefmt="%Y-%m-%d %H:%M:%S")

    # Creates a logger, adds handler for printing to screen, 
    # plus optional written copy to file "all.log"
    def __init__(self, logger_name, cre_f_ha=False, cre_sys_h=True, 
            logger_level="DEBUG", root="./", f_ha="DEBUG", sys_ha="DEBUG"):
        self.ROOT = root
        self.logger_level = getattr(logging, logger_level)

        self.logger = logging.getLogger(logger_name)
        self.logger.setLevel(self.logger_level)
        self.logger.propagate = False

        if cre_sys_h:
            self.add_handler(level=sys_ha) 
        if cre_f_ha:
            self.add_handler(level=f_ha, filename="all.log")

    # Add handlers, for either writing to file or screen
    def add_handler(self, level="NOTSET", filename=None):
        if filename == None:
            handler = logging.StreamHandler(sys.stdout)
        else:
            handler = TimedRotatingFileHandler(self.ROOT + filename, when='W0')
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

# logObj = MyLogger("test", logger_level="DEBUG")
# mlog = logObj.retrieve_logger()
# mlog.debug("hei")
# mlog.info("hei")
# mlog.warning("hei")
# mlog.error("hei")
# mlog.critical("hei")
