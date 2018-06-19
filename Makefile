LDAP=python-ldap-2.4.15
LDAPURL=https://pypi.python.org/packages/source/p/python-ldap/$(LDAP).tar.gz

FLASKSRC=https://github.com/mitsuhiko/flask.git
FLASK_BRANCH=master

# name of virtualenv tree
VENV=virtenv

all: flask flask-wtf ldap yaml

virtualenv:
	virtualenv $(VENV)

flask: virtualenv
	-mkdir src
	git clone $(FLASKSRC) -b $(FLASK_BRANCH) src/flask
	( cd src/flask ; ../../$(VENV)/bin/python setup.py install ;)
	rm -fr src/flask

flask-wtf: virtualenv flask
	$(VENV)/bin/pip install flask-wtf

yaml: virtualenv
	$(VENV)/bin/pip install PyYAML

ldap: virtualenv
	wget $(LDAPURL) && ( \
		tar xf $(LDAP).tar.gz ; \
		cd $(LDAP) ; \
		../$(VENV)/bin/python ./setup.py install ; \
		cd .. ; rm -r $(LDAP) $(LDAP).tar.gz ; \
		)

app/config.json:
	NEW_UUID=$(shell \
			 cat /dev/urandom | \
			 tr -dc 'a-zA-Z0-9' | \
			 fold -w 32 | head -n 1) ; \
	sed "s/YEK_TERCES/$${NEW_UUID}/" config.json.ex > app/config.json
	@echo "**"
	@echo "** Make sure to add the proper binddn and password to $@"
	@echo "**"

install-config: app/config.json

upstart:
	install -g root -o root -m 0644 hutchnet.conf /etc/init
	initctl reload-configuration

.PHONY: virtualenv flask ldap flask-wtf install-config

