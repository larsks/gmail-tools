#!/usr/bin/python

import os
import sys
import argparse
from configobj import ConfigObj
from validate import Validator

from StringIO import StringIO
from lxml import etree
from lxml.builder import E, ElementMaker

NSMAP = {
    'atom': 'http://www.w3.org/2005/Atom',
    'apps': 'http://schemas.google.com/apps/2006',
    }

class FilterError(Exception):
    pass

class Filter (ConfigObj):
    def __init__(self, *args, **kwargs):
        if not 'indent_type' in kwargs:
            kwargs['indent_type'] = '    '
        if not 'configspec' in kwargs:
            kwargs['configspec'] = 'filterspec.ini'
        super(Filter, self).__init__(*args, **kwargs)

    def fromxml(self, source):
        doc = etree.parse(source)

        self['filters']   = {}
        self['responses'] = {}

        author = doc.find('atom:author', namespaces=NSMAP)
        if author is not None:
            self['author'] = {
                    'name': author.find('atom:name', namespaces=NSMAP).text.strip(),
                    'email': author.find('atom:email', namespaces=NSMAP).text.strip(),
                    }

        # Load cannedResponses
        entries = doc.xpath('//atom:entry[atom:category/@term = "cannedResponse"]',
                namespaces=NSMAP)
        for entry in entries:
            id = entry.find('atom:id', namespaces=NSMAP).text
            title = entry.find('atom:title', namespaces=NSMAP).text
            content = entry.find('atom:content', namespaces=NSMAP).text

            self['responses'][id] = {
                    'title': title,
                    'content': content,
                    }

        # Load filters
        entries = doc.xpath('//atom:entry[atom:category/@term = "filter"]',
                namespaces=NSMAP)
        for entry in entries:
            id = entry.find('atom:id', namespaces=NSMAP).text
            filterdict = {}

            for prop in entry.findall('apps:property', namespaces=NSMAP):
                prop_name = prop.get('name')
                prop_val = prop.get('value')

                if prop_name == 'cannedResponse':
                    if not prop_val in self['responses']:
                        raise FilterError(
                                'undefined reference to canned response: %s' %
                                prop_val)
                elif prop_name == 'label':
                    prop_val = [prop_val]

                filterdict[prop_name] = prop_val

            self['filters'][id] = filterdict

    def toxml (self):
        doc = etree.Element('feed', nsmap=NSMAP)
        doc.append(E.title('Mail filters'))

        if 'author' in self:
            doc.append(E.author(
                E.name(self['author']['name']),
                E.email(self['author']['email']),
                ))

        for name,data in self['filters'].items():
            if data.get('cannedResponse'):
                if not data['cannedResponse'] in self['responses']:
                    raise FilterError(
                            'Undefined reference to canned response: %s' %
                            data['cannedResponse'])
                else:
                    self['responses'][data['cannedResponse']]['__used__'] = True

            if name == 'autoreply':
                print >>sys.stderr, data

            if data.get('label'):
                for label in data.as_list('label'):
                    tmpdata = dict(data)
                    tmpdata['label'] = label
                    doc.append(self.xmlfilter(name, tmpdata))
            else:
                tmpdata = dict(data)
                del tmpdata['label']
                doc.append(self.xmlfilter(name, tmpdata))

        for name, data in self['responses'].items():
            if data.get('__used__', False):
                doc.append(self.xmlresponse(name, data))

        return etree.tostring(doc, pretty_print=True)

    def xmlresponse(self, name, data):
        return E.entry(
            E.category(term='cannedResponse'),
            E.title(data['title']),
            E.id(name),
            E.content(data['content'], type='text'),
            )

    def xmlfilter(self, name, data):
        propmaker = ElementMaker(namespace=NSMAP['apps'])
        properties = []
        for k,v in data.items():
            if v is None:
                continue

            properties.append(propmaker.property(
                name=k, value=v))

        return E.entry(
            E.category(term='filter'),
            E.title('Mail filter'),
            E.id(name),
            E.content(),
            *properties
            )

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
        raise FilterError('unsupported input format.')

    check = filters.validate(Validator())
    if check is not True:
        import pprint
        pprint.pprint(check)
        raise FilterError('validation failed')

    if opts.dest == 'xml':
        print filters.toxml()
    elif opts.dest == 'ini':
        print filters.toini()
    else:
        raise FilterError('unsupported output format.')

if __name__ == '__main__':
    sys.exit(main())

