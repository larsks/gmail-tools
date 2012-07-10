#!/usr/bin/python

import os
import sys
import argparse
import configobj
from StringIO import StringIO
from lxml import etree
from lxml.builder import E, ElementMaker

NSMAP = {
    None: 'http://www.w3.org/2005/Atom',
    'atom': 'http://www.w3.org/2005/Atom',
    'apps': 'http://schemas.google.com/apps/2006',
    }

class Filter (configobj.ConfigObj):
    def fromxml(self, source):
        pass

    def fromini(self, source):
        pass

    def toxml (self):
        doc = etree.Element('feed', nsmap=NSMAP)
        doc.append(E.title('Mail filters'))
        doc.append(E.author(
            E.name(self['author']['name']),
            E.email(self['author']['email']),
            ))

        for filter,data in self.items():
            if not filter.startswith('filter:'):
                continue

            filterid = filter.split(':', 1)[1]

            propmaker = ElementMaker(namespace=NSMAP['apps'])
            properties = []
            for k,v in data.items():
                properties.append(propmaker.property(
                    name=k, value=v))

            doc.append(E.entry(
                E.category(term='filter'),
                E.title('Mail filter'),
                E.id('tag:mail.google.com,2008:filter:%s' % filterid),
                E.content(),
                *properties
                ))

        return etree.tostring(doc, pretty_print=True)

    def toini (self):
        buffer = StringIO()
        self.write(buffer)
        return buffer.getvalue()

def parse_args():
    p = argparse.ArgumentParser()

    g_in = p.add_argument_group('Input options')
    g_in.add_argument('-i', '--fromini', action='store_const',
            const='ini', dest='source')
    g_in.add_argument('-x', '--frommxl', action='store_const',
            const='xml', dest='source')

    g_out = p.add_argument_group('Output options')
    g_out.add_argument('-I', '--toini', action='store_const',
            const='ini', dest='dest')
    g_out.add_argument('-X', '--toxml', action='store_const',
            const='xml', dest='dest')

    p.set_defaults(source='xml', dest='ini')

    return p.parse_args()

def main():
    opts = parse_args()

    filters = Filter()
    doc = etree.parse(sys.stdin)

    author = doc.find('atom:author', namespaces=NSMAP)
    if author is None:
        print 'failed to find author'
        return 1

    filters['author'] = {
            'name': author.find('atom:name', namespaces=NSMAP).text.strip(),
            'email': author.find('atom:email', namespaces=NSMAP).text.strip(),
            }

    for filter in doc.findall('atom:entry', namespaces=NSMAP):
        xmlid = filter.find('atom:id', namespaces=NSMAP).text
        filterid = xmlid.split('filter:')[1]
        
        filterdict = {}

        for prop in filter.findall('apps:property', namespaces=NSMAP):
            filterdict[prop.get('name')] = prop.get('value')

        filters['filter:%s' % filterid] = filterdict

    print filters.asini()
    print filters.toxml()

if __name__ == '__main__':
    sys.exit(main())

