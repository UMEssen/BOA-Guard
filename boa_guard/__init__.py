import logging
import sys

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("boa-guard")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter("%(levelname)s:%(name)s:%(module)s:%(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)
