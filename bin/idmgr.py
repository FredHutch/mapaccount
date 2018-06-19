#!/usr/bin/env python 

import sys
import ldap
import yaml
import json
import argparse
import os.path

import logging

from collections import defaultdict
from datetime import datetime

class IDAccount( object ):
    def __init__( self, username="", alist=[], adef="" ):
        self.username = username
        self.alist = alist
        self.adef = adef

    def format( self ):
        return "user:{} alist={} adef={}".format(
            self.username,
            ",".join( self.alist ),
            self.adef
        )

class Person( object ):
    def __init__(
        self, dn="", username="", fullname="",
        title="", manager="", reports = []
    ):
        self.dn = dn
        self.username = username
        self.fullname = fullname
        self.title = title
        self.manager = manager
        self.reports = reports

    def __repr__( self ):
        #ret = ", ".join( [ self.username, ":".join( self.reports ) ] )
        ret = "Person: {}, reports: {}".format(
            self.username, str( len( self.reports ) )
        )
        return ret

    def create( self, result ):
        # populate person record from ldap data
        try:
            self.dn = result[0]
        except KeyError:
            self.dn = ""
        try:
            self.fullname = result[1]['displayName'][0]
        except KeyError:
            self.fullname = ""
        try:
            self.title = result[1]['title'][0]
        except KeyError:
            self.title = ""
        try:
            self.username = result[1]['sAMAccountName'][0]
        except KeyError:
            self.username = ""
        try:
            self.manager = result[1]['manager'][0]
        except KeyError:
            self.manager = ""
        try:
            self.reports = result[1]['directReports']
        except KeyError:
            self.reports = []

    def hasReports( self ):
        if len( self.reports ) > 0:
            return True
        else:
            return False

    def isInReports( self, search_term ):
        dn = ""
        username = ""
        try:
            tmp = DN.explode_dn( search_term )
            dn = search_term
        except:
            username = search_term

        if dn:
            for report in self.reports:
                if report.dn == dn:
                    return True
            return False
        elif username:
            for report in self.reports:
                if report.username == username:
                    return True
            return False
        else:
            raise ValueError( "DN or username not specified" )

def account_name( fullname ):
    # Clean up display name- sometimes the title is included-
    # ['Goofus MD, A. Galant']
    #   ^------^     ^
    #       |        |
    # split on spaces and use first letter found
    lname,fname = fullname.split( ', ' )
    lname = lname.split( " " )[0].lower()
    fname = fname.split( " " )[0].lower()
    actname = lname + "_" + fname[0]
    #
    # Further sanitization- special characters
    actname = actname.replace( "'", "" )
    return actname

p = argparse.ArgumentParser(
    description='return account information for a given user'
)

p.add_argument(
    '--config',
    type=str,
    default='/opt/moab/tools/idmgr/etc/config.json',
    help='location of idmgr configuration'
)
p.add_argument(
    '--logfile',
    type = str,
    default = False,
    help = 'Log errors to a file'
)
p.add_argument(
    '--debug',
    dest='dbglvl',
    action='store_true'
)
p.add_argument(
    '--no-debug',
    dest='dbglvl',
    action='store_false'
)
p.add_argument(
    'all',
    action='store'
)
p.set_defaults( dbglvl=False )

args = p.parse_args()

logger = logging.getLogger()
logfmt = logging.Formatter( '%(levelname)s: %(message)s' )

if args.dbglvl:
    logger.setLevel( logging.DEBUG )
    dbglg = logging.StreamHandler()
    dbglg.setLevel( logging.DEBUG )
    dbglg.setFormatter( logfmt )
    logger.addHandler( dbglg )
    logger.debug( "Set loglevel to debug" )
else:
    logger.setLevel( logging.INFO )

try:
    f = open( args.config, 'r' )
    config = json.load( f )
    f.close()

except IOError:
    logging.error(
        'unable to open configuration file %s',
        args.config
    )
    sys.exit( 1 )

if args.logfile:
    errlog = logging.FileHandler( args.logfile )
    errlog.setLevel( logging.INFO )
    errlog.setFormatter( logfmt )
    logger.addHandler(errlog)

time = {}
time['start'] = datetime.today()
logger.info( 'starting at ' +
            time['start'].isoformat() +
           ' with config ' + args.config )

ADServer = config['LDAP_SERVER']
ADSearchBase = config['LDAP_SEARCH_BASE']
ADSearchScope = ldap.SCOPE_SUBTREE

l = ldap.initialize( ADServer )
l.set_option(ldap.OPT_REFERRALS, 0)

try:
    l.simple_bind_s( config['BINDDN'], config['BINDPW'] )
except ldap.INVALID_CREDENTIALS, e:
    logger.error( "bind to server failed: invalid bind credentials" )
    logger.debug( e )
    sys.exit(1)
except:
    e = sys.exc_info()
    logger.error( e[0] )
    logger.exception( e[1] )
    sys.exit(1)


MemberList = config['PI_TITLES']

MemberFilter = "(&(sAMAccountType=805306368)" + "(|" 

for title in MemberList:
    MemberFilter = MemberFilter + "(title=" + title + ")"

MemberFilter = MemberFilter + "))"

Attrs = [
    "displayName",
    "directReports",
    "title",
    "manager",
    "sAMAccountName"
]

faculty = defaultdict()

try:
    search = l.search( ADSearchBase, ADSearchScope, MemberFilter, Attrs  )
    t, results = l.result( search, 60 )
except ldap.NO_SUCH_OBJECT, e:
    logger.error(
        "search base ( %s ) not found on server", ADSearchBase
    )
    logger.debug( e )
    sys.exit(1)
except ldap.REFERRAL, e:
    logger.error(
        "referral for search base ( %s ) required "+ 
        "but referrals are disabled ",
        ADSearchBase
    )
    logger.debug( e )
    sys.exit(1)
except:
    e = sys.exc_info()
    logger.error( e[0] )
    logger.exception( e[1] )
    sys.exit(1)

for result in results:
    if not result[0]:
        continue
    logger.debug( "working on %s", result[0])
    # logger.debug( result )

    tmp = Person()
    tmp.create( result )

    faculty[ tmp.dn ] = tmp

for u, person in faculty.iteritems():
    logger.debug(
        "getting reports for faculty member %s", person.username
    )
    i = 0
    while True:
        try:
            report = person.reports[i]
        except IndexError:
            break

        i = i + 1

        logger.debug( "getting info on report %s", report)
        search = l.search(
            base = report,
            scope = ldap.SCOPE_BASE,
            filterstr = "(&(sAMAccountType=805306368)(objectClass=user))",
            attrlist = Attrs
        )
        t, result = l.result( search, 60 )

        if len( result ) == 0:
            logger.debug( "%s is non person account", report )
            # remove non-person account from list of reports
            # and rewind index by one to account for its removal
            person.reports.remove( report )
            i = i - 1
            continue

        tmp = Person()
        try:
            tmp.create( result[0] )
        except:
            logger.error( "Failed creating %s", result )
            sys.exit(1)

        record = person.reports.index( report )
        person.reports[record] = tmp

        if tmp.hasReports():
            logger.debug( "found report with reports: %s", tmp.username )
            if tmp.title not in MemberList:
                logger.debug( "adding %s reports to %s",
                              tmp.username, person.username )
                person.reports = person.reports + tmp.reports
            else:
                logger.debug( "report is faculty member- skipping reports" )

accounts = defaultdict()

for member in faculty.values():
    for report in member.reports:
        aname = account_name( member.fullname )
        if accounts.has_key( report.username ):
            accounts[ report.username ].alist.append( report.username )
        else:
            accounts[ report.username ] = IDAccount(
                username = report.username,
                alist = [ aname ],
                adef = aname
            )

overrides = yaml.load_all( file( config['OVERRIDES'], 'r' ) )
# Structure of file is:
"""
---
username: username
alist: [foo,bar,baz]
adef: bar
mode: a   # 'a' indicates 'append' mode for alist
          # so alist will be [one,two,foo,bar,baz]
---
username: username
alist: [foo,bar,baz]
adef: bar
mode: r   # 'r' replaces existing alist
"""

for o in overrides:

    try:
        mode = o['mode']
    except KeyError:
        mode = 'r'

    if o.has_key('alist') and type( o['alist'] ) is not list:
        # force account list into list type- required because
        # yaml only encodes multiple entries as a list type
        o['alist'] = [ o['alist'] ]

    if not accounts.has_key( o['username'] ):
        logger.debug("Added previously unknown account %s", o['username'])
        accounts[ o['username' ] ] = IDAccount( username = o['username'] )
        mode = 'r'

    if mode == 'a':
        # Append changes
        try:
            accounts[o['username']].alist = (
                accounts[o['username']].alist +  o['alist'] 
            )
            logger.debug(
                "Appended %s to account(s) %s",
                o['username'],
                o['alist']
            )
        except KeyError:
            # "alist" not in loaded override statement
            pass

    elif mode == 'r':
        try:
            accounts[o['username']].alist = ( o['alist'] )
            logger.debug(
                "Replaced accounts for %s with account(s) %s",
                o['username'],
                o['alist']
            )
        except KeyError:
            # "alist" not in loaded override statement
            pass

    try:
        accounts[o['username']].adef = o['adef']
        logger.debug(
            "Set default account for %s with account %s",
            o['username'],
            o['adef']
        )
    except KeyError:
        # 'adef' not in override statement
        pass

for account in accounts.values():
    print account.format()

time['end'] = datetime.today()
logger.info(
    'Wrote %s credentials in %s seconds',
    len(accounts),
    time['end'] - time['start']
)

