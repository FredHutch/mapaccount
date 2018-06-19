#!/usr/bin/env python

# Get a list of the users in the "private" group and ensure
# that the entry in /etc/group matches
import MySQLdb as db
import subprocess as do
import yaml
import logging
import pyslurm
import collections

def get_account_members( s ):
    acct_db = db.connect(
        host='*******',
        user='slurm',
        db='slurm_account_db'
    )
    c = acct_db.cursor()
    c.execute( """select user from slapshot_assoc_table where acct=%s and user <> ''""", (s))
    tmp = c.fetchall()
    try:
        tmp = list( zip(*tmp)[0])
    except IndexError:
        tmp = []

    logger.debug( "got %s entries for %s", len(tmp), s )
    return( tmp )


logger = logging.getLogger()
logfmt = logging.Formatter( '%(levelname)s: %(message)s' )

logger.setLevel( logging.ERROR )
dbglg = logging.StreamHandler()
dbglg.setLevel( logging.ERROR )
dbglg.setFormatter( logfmt )
logger.addHandler( dbglg )
logger.debug( "Set loglevel to debug" )

partitions = pyslurm.partition().get()

l_groups = {}

f = open( '/etc/group', 'r' )

for l in f.readlines():
    tmp = l.rstrip().split(':')
    tmp[2] = int(tmp[2])
    if type(tmp[3]) != list:
        tmp[3] = [tmp[3]]
    l_groups[ tmp[0] ] = tmp

f.close()

for name,partition in partitions.iteritems():
    logger.debug( "checking partition %s", name )
    allow_groups = partition['allow_groups']
    if len( allow_groups ) == 0:
        logger.debug( "no group restrictions on partition" )
        continue

    tmp_grp = []
    for group in allow_groups:
        logger.debug( 'processing group %s', group )
        tmp_grp = tmp_grp + get_account_members( group )

    l_groups[ name ][3] = tmp_grp


l_groups = collections.OrderedDict(
    sorted( l_groups.items(), key=lambda t: t[1][2])
)


for group in l_groups.keys():
    print ':'.join( l_groups[group][0:2] +
                   [str( l_groups[group][2] ) ]+
                        [",".join( l_groups[group][3])] )

