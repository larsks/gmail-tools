#!/usr/bin/python

import os
import sys
import argparse
import imaplib
import logging
import configobj
import datetime

global log

class IMAPCommandFailed(Exception):
    pass

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument('-f', '--cfgfile', default='expire.cf')
    p.add_argument('-n', '--dryrun', action='store_true')
    p.add_argument('-d', '--debug', action='store_true')
    p.add_argument('--trace', action='store_true')
    return p.parse_args()

def uidcommand(server, *args):
    response = server.uid(*args)
    log.debug('command=%s, response=%s' % (args[0], response[0]))
    if response[0] != 'OK':
        raise IMAPCommandFailed(response)

    return response

def main():
    global log

    opts = parse_args()
    logging.basicConfig(level=logging.DEBUG if opts.debug else logging.INFO)
    log = logging.getLogger('expire')

    log.debug('Reading config from %s' % opts.cfgfile)
    cfg = configobj.ConfigObj(opts.cfgfile)
    default = cfg.get('filter:default', {})

    log.info('Connecting to %(host)s (port %(port)s).' % cfg['server'])
    server = imaplib.IMAP4_SSL(
            cfg['server']['host'],
            cfg['server']['port'])

    if opts.trace:
        server.debug=4

    log.info('Logging in as %(user)s' % cfg['server'])
    server.login(
            cfg['server']['user'],
            cfg['server']['password'])

    for section, data in cfg.items():
        if section.startswith('filter:') and section != 'filter:default':
            filter_name = section[len('filter:'):]
            log.debug('Processing filter %s' % filter_name)

            fconfig = dict(default)
            fconfig.update(data)

            if opts.debug:
                for k,v in fconfig.items():
                    log.debug('%s %s = %s' % (filter_name, k, v))

            try:
                action = fconfig['action'].split(':', 1)
            except ValueError:
                action = (fconfig['action'], None)

            server.select(fconfig['folder'])

            date_age_days_ago = (
                    datetime.datetime.now() -
                    datetime.timedelta(days=int(fconfig['age']))
                    )
            age_filter = 'before:%s' % (
                    date_age_days_ago.strftime('%Y-%m-%d'))

            log.debug('age_filter is %s' % age_filter)

            response = uidcommand(server, 'SEARCH', 'X-GM-RAW',
                    '%s (%s)' % (age_filter, fconfig['filter']))
            results = response[1][0].split()

            log.info('filter %s will %s %d messages.' % (
                    filter_name, action[0], len(results)))
            if opts.dryrun:
                continue
            if len(results) == 0:
                continue

            if action[0] == 'delete':
                uidcommand(server, 'copy', ','.join(results),
                        '[Gmail]/Trash')
#                uidcommand(server, 'store',
#                        ','.join(results), '+FLAGS', '(\\Deleted)')
            elif action[0] == 'move' or action[0] == 'copy':
                uidcommand(server, 'copy', ','.join(results), action[1])
                if action[0] == 'move':
                    uidcommand(server, 'store',
                            ','.join(results), '+FLAGS', '(\\Deleted)')
            elif action[0] == 'label':
                pass

            response = server.expunge()
            log.debug('expunge response=%s' % response[0])

if __name__ == '__main__':
    main()

