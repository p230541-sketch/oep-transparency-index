import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from webapp.app import app as _app

app = _app
handler = _app
application = _app
