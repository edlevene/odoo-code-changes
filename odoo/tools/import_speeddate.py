import os
import sys
import logging

_logger = logging.getLogger(__name__)

fpath = os.path.join(os.path.dirname(__file__), 'speeddate')
_logger.info("## ## ## fpath = %s", fpath)
_logger.info("## ## ## APPENDING fpath TO sys.path !")

sys.path.append(fpath)