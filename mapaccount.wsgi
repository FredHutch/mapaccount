import sys
activate_this = '/var/www/toolbox/mapaccount/virtenv/bin/activate_this.py'
execfile( activate_this, dict(__file__=activate_this))
sys.path.insert(0, '/var/www/toolbox/mapaccount')
sys.path.insert(0, '/var/www/toolbox/mapaccount/virtenv/bin')
from app import app as application
