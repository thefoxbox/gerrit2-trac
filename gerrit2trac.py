#!/usr/bin/python
#
# gerrit2trac.py - Update Trac tickets via Gerrit Code Review hooks
#
# Copyright (C) 2013 Eric Fox <eric@thefoxbox.com>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Gerrit2Trac

A Python utility for updating Trac tickets via Gerrit Code Review hooks.
"""

__version__ = '1.0.0'

import ConfigParser
import json
import re
import sys
from email.utils import parseaddr
from optparse import OptionParser, OptionGroup
from string import Template
from time import time
from urllib2 import urlopen, HTTPError, URLError
from urlparse import urlparse
from xmlrpclib import ServerProxy, ProtocolError


def process_options(arglist=None):
    """
    Process options passed via command line args.

    These are "most" of the options listed in the Gerrit hooks documentation.
    """
    usage = 'Usage: %prog [option] [hook] <parameter>'
    parser = OptionParser(version=__version__, usage=usage)
    parser.add_option('-v',
                      action='store_true', help='verbose output', default=False)
    parser.add_option('-c',
                      metavar='FILE', action='store',
                      default='/opt/gerrit2/etc/gerrit2trac.config',
                      help='configuration (default: %default)')
    group = OptionGroup(parser, "Parameters")
    group.add_option('--change',
                     metavar='<change id>', action='store', default=None)
    group.add_option('--is-draft', dest='isdraft',
                     metavar='<boolean>', action='store_true', default=0)
    group.add_option('--change-url', dest='changeurl',
                     metavar='<change url>', action='store', default=None)
    group.add_option('--project',
                     metavar='<project name>', action='store', default=None)
    group.add_option('--branch',
                     metavar='<branch>', action='store', default=None)
    group.add_option('--topic',
                     metavar='<topic>', action='store', default=None)
    group.add_option('--uploader',
                     metavar='<uploader>', action='store', default=None)
    group.add_option('--commit',
                     metavar='<sha1>', action='store', default=None)
    group.add_option('--patchset',
                     metavar='<patchset id>', action='store', default=None)
    group.add_option('--author',
                     metavar='<author>', action='store', default=None)
    group.add_option('--comment',
                     metavar='<comment>', action='store', default=None)
    group.add_option('--Code-Review', dest='codereview',
                     metavar='<score>', action='store', default=None)
    group.add_option('--Verified', dest='verified',
                     metavar='<score>', action='store', default=None)
    group.add_option('--reviewer',
                     metavar='<reviewer>', action='store', default=None)
    group.add_option('--submitter',
                     metavar='<submitter>', action='store', default=None)
    group.add_option('--abandoner',
                     metavar='<abandoner>', action='store', default=None)
    group.add_option('--restorer',
                     metavar='<restorer>', action='store', default=None)
    group.add_option('--oldrev',
                     metavar='<sha1>', action='store', default=None)
    group.add_option('--newrev',
                     metavar='<sha1>', action='store', default=None)
    group.add_option('--refname',
                     metavar='<ref name>', action='store', default=None)
    group.add_option('--reason',
                     metavar='<reason>', action='store', default=None)
    parser.add_option_group(group)
    (options, args) = parser.parse_args()
    if len(args) > 2:
        parser.error('Too many arguments')
    if options.change is None:
        parser.error('Missing required parameter: change')
    return options, args


def trac_ticket_actions(options, config, hook=None):
    """ Define ticket update attributes."""

    comment = cc = None
    action = 'leave'

    # ref-updated
    if hook == 'ref-updated':
        workflow = 'ref_updated'
        comment = 'Ref updated.'
    # patchset-created
    elif hook == 'patchset-created':
        workflow = 'patchset_created'
        comment = 'Patchset created.'
    # draft-published
    elif hook == 'draft-published':
        workflow = 'draft_published'
        comment = 'Draft published'
    # comment-added
    elif hook == 'comment-added':
        workflow = 'comment_added'
        comment = 'Comment added'
    # change-merged
    elif hook == 'change-merged':
        workflow = 'change_merged'
        comment = 'Change merged.'
        action = 'resolve'
    # merge-failed
    elif hook == 'merge-failed':
        workflow = 'merge_failed'
        comment = 'Merge failed.'
    # change-abandoned
    elif hook == 'change-abandoned':
        workflow = 'change_abandoned'
        comment = 'Change abandoned.'
    # change-restored
    elif hook == 'change-restored':
        workflow = 'change_restored'
        comment = 'Change restored.'
    # ref-updated
    elif hook == 'ref-updated':
        workflow = 'ref_updated'
        comment = 'Ref updated.'
    # reviewer-added
    elif hook == 'reviewer-added':
        workflow = 'reviewer_added'
        comment = 'Reviewer added.'
    # topic-changed
    elif hook == 'topic-changed':
        workflow = 'topic_changed'
        comment = 'Topic changed.'
    # default
    else:
        workflow = None
        comment = 'Gerrit2Trac submitted this comment.'

    if config.has_option('workflow', workflow + '.comment'):
        comment = Template(
            config.get('workflow', workflow + '.comment')
            ).safe_substitute(vars(options))
    else:
        comment = comment
    if config.has_option('workflow', workflow + '.action'):
        action = config.get('workflow', workflow + '.action')
    else:
        action = action
    if config.has_option('workflow', workflow + '.cc'):
        cc = Template(
            config.get('workflow', workflow + '.cc')
            ).safe_substitute(vars(options))
    return comment, action, cc


def trac_ticket_cc(ticket, cc):
    """ Returns a formatted string of current and new ticket CC addresses. """

    emails = []
    if ticket:
        for i, attr in enumerate(ticket):
            if isinstance(attr, dict):
                if attr['cc']:
                   emails.extend([x.strip() for x in attr['cc'].split(',')])
    if cc:
        for addr in cc.split(','):
            # Gerrit uses parenthesis to enclose email addresses in
            # hook parameters.
            # The following line was added as a work-around.
            addr = addr.replace('(', '<').replace(')', '>')
            if '@' in parseaddr(addr)[1]:
                emails.extend([parseaddr(addr)[1]])
    return ', '.join(set(emails))


def main():
    (options, args) = process_options()

    verbose = options.v
    hook = None
    if args:
        hook = args[0]

    config = ConfigParser.SafeConfigParser()
    config.read(options.c)
    trac_url = config.get('trac', 'xmlrpcweburl')
    trac_user = config.get('trac', 'username')
    trac_pass = config.get('trac', 'password')
    gerrit_url = config.get('gerrit', 'canonicalweburl')

    # Query Gerrit REST API and store reponse.
    #
    # Gerrit includes a "magic prefix" in all REST responses which
    # needs to be stripped in order to form a valid JSON response.
    gerrit_request = (gerrit_url + '/changes/?q=' + options.change +
                      '&o=CURRENT_REVISION&o=CURRENT_COMMIT&o=CURRENT_FILES')
    try:
        if verbose:
            print 'Sending request: ' + gerrit_request
        response = urlopen(gerrit_request)
        data = []
        if verbose:
            print 'Reading response:'
        for line in response:
            if line.strip() == str(')]}\''):
                continue
            data.append(line)
        response.close()
        if data:
            change = json.loads(''.join(data))
    except HTTPError as e:
        print e.code
    except URLError as e:
        print e.reason.args[1]

    # Store commit message from JSON response string.
    if change:
        if verbose:
            print 'Reading change commit message:'
        if options.commit is None:
            options.commit = change[0]['current_revision']
        message = change[0]['revisions'][options.commit]['commit']['message']
    else:
        print 'Exiting: No results found for change ' + options.change
        sys.exit(0)

    # Check whether the commit message has a ticket reference.
    if verbose:
        print 'Searching commit message for ticket reference:'
    m = re.search('^ticket:\s*#*(\d+)$', message, flags=re.I|re.M)
    if m:
        ticket_id = m.group(1)
    else:
        print 'Exiting: Ticket reference not found in commit message'
        sys.exit(0)

    # Define Trac ticket update attributes per hook.
    (comment, action, cc) = trac_ticket_actions(options, config, hook)
    update_attr = {
        'action': action,
        'ts': str(int(time() * 1000000.0))
        }

    # Query Trac XMLRPC interface and update the referenced ticket.
    o = urlparse(trac_url)
    trac_url_auth = (o.scheme + '://' + trac_user + ':' + trac_pass + '@' +
                     o.netloc + o.path)
    server = ServerProxy(trac_url_auth)
    if cc:
        try:
            if verbose:
                print 'Reading current ticket Cc: attributes:'
            ticket = server.ticket.get(ticket_id)
        except ProtocolError as e:
            print 'Error: ' + e.errmsg
            sys.exit(1)
        if ticket:
            update_attr['cc'] = trac_ticket_cc(ticket, cc)
    if verbose:
        print ('Modifications for Trac ticket ' + ticket_id + ':\n' +
                str(update_attr))
    try:
        if verbose:
            print 'Sending ticket.update() request:'
        server.ticket.update(ticket_id, comment, update_attr, False)
    except ProtocolError as e:
        print 'Error: ' + e.errmsg
        sys.exit(1)
    if verbose:
        print 'Successfully updated Trac ticket!'

if __name__ == "__main__":
    main()

