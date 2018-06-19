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

import subprocess

class Person( object ):
    def __init__(
        self, dn="", username="", fullname="",
        title="", manager="", reports = [],
        division="", alist = [], adef=None
    ):
        self.dn = dn
        self.username = username
        self.fullname = fullname
        self.title = title
        self.manager = manager
        self.reports = reports
        self.division = division
        self.adef = adef

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
        try:
            self.division = result[1]['division'][0]
        except KeyError:
            self.division = ""

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

        return retval

class Account( object ):
    def __init__( self, name = None, owner = None, members = []):
        self.name = name
        self.owner = owner
        self.members = members

    def username( self ):
        return self.owner.username

    def fullname( self ):
        return self.owner.fullname

    def division( self ):
        return self.owner.division

    def append_member( self, name ):
        if name not in self.members:
            self.members.append( name )

        return

    def account_name( self ):
        if self.name is None:
            # Clean up display name- sometimes the title is included-
            # ['Goofus MD, A. Galant']
            #   ^------^     ^
            #       |        |
            # split on spaces and use first letter found
            lname,fname = self.fullname().split( ', ' )
            lname = lname.split( " " )[0].lower()
            fname = fname.split( " " )[0].lower()
            actname = lname + "_" + fname[0]
            #
            # Further sanitization- special characters
            actname = actname.replace( "'", "" )
            return actname
        else:
            return self.name

    def format( self, format='slurm' ):
        if format == 'slurm':
            fmt = ( "Account - {}:" +
                   "Description='{}':" +
                   "Organization='{}'"
                  )
            return fmt.format(
                self.account_name(),
                self.fullname(),
                self.division() )

def existing( entity, name ):
    # return true/false for existence of entity in database

    if not ( entity == 'account' or entity == 'user') :
        raise ValueError( "entity must be account or user" )

    cmd = '/usr/bin/sacctmgr'
    opts = [ '--parsable', '--immediate', '--quiet', '--noheader' ]

    try:
        output = subprocess.check_output(
            [ cmd ] + opts + [ 'show', entity, name ]
        )
    except subprocess.CalledProcessErr, err:
        logging.error( "failed testing existence of {}".format( name ) )
        raise RuntimeError( 'function "existing" failed' )

    if name in output:
        return True
    else:
        return False


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
    '--format',
    type=str,
    default='mwm',
    help='Output format- valid options are "mwm", "slurm", and "yaml"'
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
    "sAMAccountName",
    "division"
]


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

accounts = defaultdict()
people = defaultdict()

for result in results:
    if not result[0]:
        continue
    logger.debug( "working on %s", result[0])

    member = Person()
    member.create( result )

    account = Account( owner = member, members=member.reports )
    accounts[ account.account_name() ] = account

    people[ member.username ] = member
    people[ member.username ].adef = account.account_name()

for u, account in accounts.iteritems():
    logger.debug(
        "getting reports for faculty member %s", account.owner.username
    )
    i = 0
    while True:
        try:
            report = account.members[i]
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
            account.members.remove( report )
            i = i - 1
            continue

        tmp = Person()
        try:
            tmp.create( result[0] )
        except:
            logger.error( "Failed creating %s", result )
            sys.exit(1)

        record = account.members.index( report )
        account.members[record] = tmp.username
        if tmp.username not in people:
            people[ tmp.username ] = tmp
            people[ tmp.username ].adef = account.account_name()

        # Append list of reports-to-report to the parent so long
        # as the report is not in MemberList (i.e. faculty)
        if tmp.hasReports():
            logger.debug( "found report with reports: %s (%s)",
                         tmp.username, tmp.title )
            if tmp.title not in MemberList:
                logger.debug( "adding %s's reports to %s (%s)",
                              tmp.username, account.owner.username,
                            tmp.reports )
                account.members = account.members + tmp.reports
            else:
                logger.debug( "report is faculty member- skipping reports" )

    logger.debug("done with for faculty member %s", account.owner.username)


overrides = yaml.load_all( file( config['OVERRIDES'], 'r' ) )
logger.debug("processing account overrides")
for o in overrides:
    try:
        o['account'] is not None
    except KeyError:
        continue

    filter = (
        "(&" +
        "(sAMAccountType=805306368)" +
        "(objectClass=user)" +
        "(sAMAccountName={})".format(o['owner']) +
        ")"
    )
    search = l.search(
        base = ADSearchBase,
        scope = ldap.SCOPE_SUBTREE,
        filterstr = filter,
        attrlist = Attrs
    )
    t, result = l.result( search, 60 )

    #logger.debug( "len result is %s", len(result))
    if len( result ) == 0:
        logger.error( "account %s not found", o['account'] )

    tmp = Person()
    try:
        tmp.create( result[0] )
    except:
        logger.error( "Failed creating %s", result )
        sys.exit(1)

    if tmp.username not in people:
        logger.error(
            "override account owner %s does not exist", tmp.username
        )
        continue
    else:
        logger.debug( "found account owner %s", tmp.username )

    account = Account(
        name = o['account'],
        owner = people[ tmp.username ],
        members = []
    )
    accounts[ account.account_name() ] = account
    logger.debug("created account %s from override", account.account_name() )

overrides.close()

overrides = yaml.load_all( file( config['OVERRIDES'], 'r' ) )
logger.debug("processing user overrides")
for o in overrides:
    try:
        o['username'] is not None
    except KeyError:
        continue

    if o['username'] not in people:
        logging.error( "Unknown username %s found", o['username'] )
        continue

    if o.has_key('alist') and type( o['alist'] ) is not list:
        # force account list into list type- required because
        # yaml only encodes multiple entries as a list type
        o['alist'] = [ o['alist'] ]

    for account in o['alist']:

        if account.lower() == "all":
            logger.info( "user %s is allowed all access", o['username'] )
            for a in accounts.values():
                a.append_member( o['username'] )
                logger.debug(
                    "all access appended user %s to %s",
                    o['username'],
                    a.account_name()
                )
            continue

        if account not in accounts:
            logger.error(
                "unknown account %s specified in overrides- ignored",
                account
            )
            continue
        try:
            accounts[account].append_member( o['username'] )
            logger.debug(
                "Appended %s to account(s) %s",
                o['username'],
                account
            )
        except KeyError:
            # "alist" not in loaded override statement
            pass

    if not o.has_key('adef'):
        logger.info(
            "no default account for %s specified in overrides", account
        )
        continue

    if o['adef'] not in accounts:
        logger.error(
            "unknown default account %s specified in overrides- ignored",
            account
        )
        continue
    else:
        try:
            people[o['username']].adef = o['adef']
            logger.debug(
                "Set default account for %s with account %s",
                o['username'],
                o['adef']
            )
        except KeyError:
            # 'adef' not in override statement
            pass

overrides.close()

# Print header
print( "Cluster - slapshot" )
print( "Parent - root" )
print( "User - root:DefaultAccount='root':" +
      "AdminLevel='Administrator':Fairshare=1" )

print( "Account - admin:Description='top level account':Organization='fhcrc':Fairshare=1" )
print( "Account - rsrch:Description='top level account for center researchers':Organization='fhcrc':Fairshare=10:QOS='full,grabnode,normal,restart'" )



for account in accounts.values():
    print (
        account.format( format="slurm" ) +
        ":Fairshare=10:GrpCPUs=125:QOS='full,grabnode,normal,restart'" )

for account in accounts.values():
    print "Parent - {}".format( account.account_name() )
    print "User - solexa:DefaultAccount='sr_genomics':Fairshare=2147483647"
    print "User - {}:DefaultAccount='{}':Fairshare=2147483647".format(
        account.owner.username, people[ account.owner.username ].adef
    )
    for report in account.members:
        print "User - {}:DefaultAccount='{}':Fairshare=2147483647".format(
            people[ report ].username, people[ report ].adef
        )


sys.exit(0)
