#!/usr/bin/env python2.7
# -*- coding: UTF-8 -*-

from sets import Set
import sys
import ldap
import yaml

from flask import render_template, flash, redirect
from flask import jsonify
from flask import request
from app import app
from forms import MapAccountForm

import logging
logging.basicConfig( level = logging.DEBUG )

def get_manager( connection, dn ):
    """
    returns the manager for the entity with the given dn.
    """
    search = connection.search(
        base=dn,
        scope=ldap.SCOPE_BASE,
        attrlist=[ 'manager' ]
    )
    type, result = connection.result( search, 60 )
    return result[0][1]['manager'][0]

def get_title( connection, dn ):
    """
    returns the title for the entity with the given dn.
    """
    search = connection.search(
        base=dn,
        scope=ldap.SCOPE_BASE,
        attrlist=[ 'title' ]
    )
    type, result = connection.result( search, 60 )
    return result[0][1]['title'][0]

def generate_account( connection, dn ):
    search = connection.search(
        base=dn,
        scope=ldap.SCOPE_BASE,
        attrlist=[ 'sn', 'givenName' ]
    )
    type, result = connection.result( search, 60 )
    attrs = result[0][1]
    return [ attrs['sn'][0].lower() + "_" + attrs['givenName'][0].lower()[0] ]

def process_overrides( uid, accounts=[] ):
    found = False
    for o in yaml.load_all( file( app.config['OVERRIDES'], 'r' ) ):
        try:
            if o[ 'username' ] == uid:
                found = True
                try:
                    mode = o[ 'mode' ]
                except KeyError:
                    mode = 'r'

                logging.debug(
                    "Adding accounts %s with mode %s",
                    o['alist'],
                    mode
                )
                if mode == 'r':
                    accounts = o[ 'alist' ]
                elif mode == 'a':
                    accounts = accounts + o[ 'alist' ]
                else:
                    logging.error(
                        'Unknown mode %s found in overrides file', mode
                    )
        except KeyError:
            logging.debug( "Skipping non-username entry" )
            continue

    if found:
        return accounts
    else:
        return []

def map_uid( uids ):
    ADServer = "ldap://dc.fhcrc.org"
    ADServer = app.config[ 'LDAP_SERVER' ]
    ADSearchBase = "dc=fhcrc,dc=org"
    ADSearchBase = app.config[ 'LDAP_SEARCH_BASE' ]
    ADSearchScope = ldap.SCOPE_SUBTREE

    l = ldap.initialize( ADServer )
    l.set_option(ldap.OPT_REFERRALS, 0)
    l.simple_bind_s( app.config['BINDDN'], app.config['BINDPW'] )


    filter_base = "(&" + "(sAMAccountType=805306368)" + "(fhcrcpaygroup=Y)"
    search_attrs = [ "sAMAccountName", "manager", ]

    results = {}

    for uid in uids:
        filter = filter_base + "(sAMAccountName=" + uid + "))"

        p = l.search( ADSearchBase, ADSearchScope, filter, search_attrs )
        type, person = l.result( p, 60 )

        if len(person) != 2:
            if len(person) == 1:
                logging.debug( "No data found for %s", uid )
                results[ uid  ] = []
            if len(person) > 2 :
                logging.debug( "Bizzare number of results (%s) found",
                               len(person)
                             )
                results[ uid  ] = []

            if process_overrides( uid ) is not None:
                results[ uid ] = process_overrides( uid )
            else:
                logging.debug( "No override found for %s", uid )
            continue

        logging.debug( "found record: %s", person )
        if get_title(l, person[0][0]) in app.config['PI_TITLES']:
            results[ person[0][1]['sAMAccountName'][0] ] = (
                generate_account( l, person[0][0] )
            )
            logging.debug(
                "get_title() is true: person found in list of PI titles"
            )
            continue

        try:
            manager = person[0][1]['manager'][0] 
        except KeyError:
            manager = "NA"
            continue
        logging.debug( "manager set to %s", manager )

        for locate in range(app.config['MAXTRIES']):
            manager_title = get_title( l, manager )
            if get_title( l, manager ) in app.config['PI_TITLES']:
                results[ person[0][1]['sAMAccountName'][0] ] = ( 
                    generate_account( l, manager )
                )
                logging.debug( "found valid pi title %s for %s", 
                              manager_title, manager
                             )
                break
            else:
                try:
                    manager = get_manager( l, manager )
                except KeyError:
                    results[ person[0][1]['sAMAccountName'][0] ] = (
                        generate_account( l, manager )
                    )
                    break
        else:
            continue

        logging.debug( "results before overrides: %s", results )
        logging.debug( "processing overrides for %s", uid )
        overrides = process_overrides( uid )
        logging.debug( "found overrides: %s", overrides )

        tmp = results[ person[0][1]['sAMAccountName'][0] ]
        tmp.extend( override for override in overrides if override not in tmp )

        results[ person[0][1]['sAMAccountName'][0] ] = ( tmp )

    return results

@app.route( '/rest/<uid>', methods = [ 'GET' ] )
def mapaccount_rest(uid):
    return jsonify( map_uid([ uid ]) )

@app.route( '/form', methods = [ 'GET', 'POST' ] )
def mapaccount_post():
    # this will have the form & upload list of uids via the post
    # uids = something
    form = MapAccountForm()

    if request.method == "POST":
        print "submitting"
        uids = request.form['uids'].replace( " ", "" )
        uids = uids.split(',')
        return jsonify( map_uid( uids ) )

    return render_template('uids.html', title='Enter UIDs', form = form )


