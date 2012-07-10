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

class FilterError(Exception):
    pass

class Filter (configobj.ConfigObj):
    def fromxml(self, source):
        doc = etree.parse(source)

        author = doc.find('atom:author', namespaces=NSMAP)
        if author is not None:
            self['author'] = {
                    'name': author.find('atom:name', namespaces=NSMAP).text.strip(),
                    'email': author.find('atom:email', namespaces=NSMAP).text.strip(),
                    }

        for filter in doc.findall('atom:entry', namespaces=NSMAP):
            xmlid = filter.find('atom:id', namespaces=NSMAP).text
            filterid = xmlid.split('filter:')[1]
            
            filterdict = {}

            for prop in filter.findall('apps:property', namespaces=NSMAP):
                filterdict[prop.get('name')] = prop.get('value')

            self['filter:%s' % filterid] = filterdict

    def toxml (self):
        doc = etree.Element('feed', nsmap=NSMAP)
        doc.append(E.title('Mail filters'))

        if 'author' in self:
            doc.append(E.author(
                E.name(self['author']['name']),
                E.email(self['author']['email']),
                ))

        for name,data in self.items():
            if not name.startswith('filter:'):
                continue

            if 'label' in data:
                for label in data.as_list('label'):
                    tmpdata = dict(data)
                    tmpdata['label'] = label
                    doc.append(self.xmlfilter(name, tmpdata))
            else:
                doc.append(self.xmlfilter(name, data))

        return etree.tostring(doc, pretty_print=True)

    def xmlfilter (self, name, data):
        filterid = name.split(':', 1)[1]
        filter = E.entry()

        propmaker = ElementMaker(namespace=NSMAP['apps'])
        properties = []
        for k,v in data.items():
            properties.append(propmaker.property(
                name=k, value=v))

        filter.append(E.entry(
            E.category(term='filter'),
            E.title('Mail filter'),
            E.id('tag:mail.google.com,2008:filter:%s' % filterid),
            E.content(),
            *properties
            ))

        return filter

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
    g_in.add_argument('--input', '--in')

    g_out = p.add_argument_group('Output options')
    g_out.add_argument('-I', '--toini', action='store_const',
            const='ini', dest='dest')
    g_out.add_argument('-X', '--toxml', action='store_const',
            const='xml', dest='dest')
    g_out.add_argument('--output', '--out')

    p.set_defaults(source='xml', dest='ini')

    return p.parse_args()

def main():
    opts = parse_args()

    if opts.input:
        sys.stdin = open(opts.input, 'r')
    if opts.output:
        sys.stdout = open(opts.output, 'w')

    if opts.source == 'xml':
        filters = Filter()
        filters.fromxml(sys.stdin)
    elif opts.source == 'ini':
        filters = Filter(sys.stdin)
    else:
        raise FilterError('Unsupported input format.')

    if opts.dest == 'xml':
        print filters.toxml()
    elif opts.dest == 'ini':
        print filters.toini()
    else:
        raise FilterError('Unsupported output format.')

if __name__ == '__main__':
    sys.exit(main())

