from flask import Flask
from flask import json

app = Flask(__name__)
#app.config.from_object( 'config')
app.config.from_json( 'config.json')

from app import views
from app import mapaccount

