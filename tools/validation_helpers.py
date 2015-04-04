#! /usr/bin/env python

import json
import logging
import sys

import pypandoc
import pandocfilters

import filters.common as fc

try:  # Hack to make codebase compatible with python 2 and 3
  basestring
except NameError:
  basestring = str


# Common validation functions
def is_list(text):
    """Validate whether the provided string can be converted to python list"""
    # FIXME: deprecated
    text = text.strip()
    try:
        text_as_list = json.loads(text)
    except ValueError:
        logging.debug("Could not convert string to python object: {0}".format(text))
        return False

    return isinstance(text_as_list, list)


def is_str(text):
    """Validate whether the input is a non-blank python string"""
    # FIXME: Maybe deprecated?
    return isinstance(text, basestring) and len(text) > 0


def is_numeric(text):
    """Validate whether the string represents a number (including unicode)"""
    try:
        float(text)
        return True
    except ValueError:
        return False


def node_or_root(f):
    """Class method decorator: if no node is specified, use root node"""
    def decorator(self, ast_node, *args, **kwargs):
        if ast_node is None:
            ast_node = self.body
        return f(self, ast_node, *args, **kwargs)
    return decorator


### Helper objects
class PandocAstHelper(object):
    """Basic helper functions for working with the internal abstract syntax
    tree produced by Pandoc parser"""
    def __init__(self, markdown):
        self.ast_root, self.header, self.body = self._parse_markdown(markdown)

    @staticmethod
    def _parse_markdown(markdown):
        """
        Parse the provided markdown string
        """
        ast = json.loads(pypandoc.convert(markdown,
                                          'json',
                                          'markdown'))
        headers = ast[0]["unMeta"]
        body = ast[1]
        return ast, headers, body

    @staticmethod
    def ast_to_string(ast_node):
        """Convert Pandoc AST to string."""
        return pandocfilters.stringify(ast_node)

    # Helpers to get information from a specific node type
    def get_heading_info(self, heading_node):
        """Get heading text, level, and list of all css styles applied"""
        if not self.is_heading(heading_node):
            raise TypeError("Cannot apply this method to something that is not a heading")

        text = self.ast_to_string(heading_node)
        level = heading_node['c'][0]
        box_styles = heading_node['c'][1][1]  # List of all styles
        return text, level, box_styles

    def get_box_info(self, box_node):
        """Given a callout box, return the title, level, and [styles] for
        the heading node."""
        if not self.is_box(box_node):
            raise TypeError("Cannot apply this method to something that is not a box")

        box_heading = box_node['c'][0]
        title, level, styles = self.get_heading_info(box_heading)
        return title, level, styles

    def get_link_info(self, link_node):
        """Given a link node, return the link title and destination"""
        # ToDO: implement fetching of link info
        # FIXME: For refactoring, this change switches the order of function outputs
        if not self.is_external(link_node):
            raise TypeError("Cannot apply this method to something that is not a link")

        link_text = self.ast_to_string(link_node)
        dest_url = self.get_children(link_node)[1][0]

        return link_text, dest_url

    # Functions to fetch specific parts of the document
    @node_or_root
    def get_children(self, ast_node=None):
        """Get children of node, if any are defined"""
        return ast_node.get('c', [])

    def get_header_field(self, field_label):
        """Fetch the value of one field from the document YAML headers.
        If the field label is not present, return None for display purposes"""
        # TODO: does this need to be rewritten?
        return self.header.get(field_label, None)

    # Helpers to fetch specific document sections
    @node_or_root
    def get_section_headings(self, ast_node=None):
        """Return a list of headings as (title, level, styles) tuples"""
        # FIXME: This changes the order of outputs vs original version
        # TODO: consider returning raw heading nodes for consistency?
        return [self.get_heading_info(n)
                for n in ast_node if self.is_heading(n)]

    @node_or_root
    def get_boxes(self, ast_node=None):
        return [n for n in ast_node['c']
                if self.is_box(n)]

    @node_or_root
    def get_doc_anchors(self, ast_node=None):
        """Get a list of known anchors (places a link can go)
        that are present in the document (or below the given node)"""
        anchors = []

        def get_anchors(key, val, format, meta):
            if key == "Header":
                anchors.append(val[1][0])
            if key == "DefinitionList":
                for definition in val:
                    anchor_label = fc.text2fragment_identifier(
                        self.ast_to_string(definition[0]))
                    anchors.append(anchor_label)

        pandocfilters.walk(ast_node, get_anchors, "", {})
        return anchors

    @node_or_root
    def find_external_links(self, ast_node=None, parent_crit=None, _ok=False):
        # TODO: Update this function
        """Recursive function that locates all references to external content
         under specified node. (links or images)

         User can optionally provide a `parent_crit` function to filter link
           list based on where link appears. (eg, only links in headings)
        If no filter is provided, accept all links.

        The parameter `_ok` is used internally to track whether parent
          criterion was met
         """

        # Check whether this node (or any children) contains an accepted link
        if parent_crit is None:
            accept = True
        else:
            accept = _ok or parent_crit(ast_node)

        links = []
        if self.is_external(ast_node):
            links.append(ast_node)

        # Also look for links in child nodes.
        for n in self.get_children(ast_node):
            links.extend(self.find_external_links(n,
                                                  parent_crit=parent_crit,
                                                  _ok=accept))

        return links

    # Functions to query type or content of nodes
    def has_section_heading(self, section_title, ast_node=None,
                            heading_level=2, limit=sys.maxsize, show_msg=True):
        """Does the section contain (<= x copies of) specified heading text?
        Will strip off any CSS attributes when looking for the section title"""
        # TODO: Alternate Raniere implementation may deprecate this?
        if ast_node is None:
            ast_node = self.ast_root

        num_nodes = len([ti
                         for ti, lvl, _ in self.get_section_headings(ast_node)
                         if ti == section_title
                         and (lvl == heading_level)])

        # Suppress error msg if used as a helper method
        if show_msg and num_nodes == 0:
            logging.error("Document does not contain the specified "
                          "heading: {0}".format(section_title))
        elif show_msg and num_nodes > limit:
            logging.error("Document must not contain more than {0} copies of"
                          " the heading {1}".format(limit, section_title or 0))
        elif show_msg:
            logging.info("Verified that document contains the specified"
                         " heading: {0}".format(section_title))
        return (0 < num_nodes <= limit)

    # TODO: End untouched section

    def has_number_children(self, ast_node,
                            exact=None, minc=0, maxc=sys.maxsize):
        """Does the specified node (such as a bulleted list) have the expected
         number of children?"""

        if exact:  # If specified, must have exactly this number of children
            minc = maxc = exact

        return (minc <= len(ast_node['c']) <= maxc)

    # Helper functions to improve readability of code that works on the AST
    def is_heading(self, ast_node, heading_level=None):
        """Is the node a heading/ title?
        (Optional: check that it is a specific heading level)"""
        has_tag = (ast_node['t'] == "Header")

        if heading_level is None:
            has_level = True
        else:
            #FIXME: This is a different method of level vs self.get_heading_info; resolve discrepancy
            level = (self.ast_to_string(ast_node['c'][2]))
            has_level = (level == heading_level)
        return has_tag and has_level

    def is_paragraph(self, ast_node):
        """Is the node a paragraph?"""
        return ast_node['t'] == "Para"

    def is_list(self, ast_node):
        """Is the node a list? (ordered or unordered)"""
        return ast_node['t'] == "BulletList" or "OrderedList"

    def is_external(self, ast_node):
        """Does the node reference content outside the file? (image or link)"""
        return ast_node['t'] in ("Link", "Image")

    def is_block(self, ast_node):
        """Is the node a BlockQuoted element?"""
        return ast_node['t'] == "BlockQuote"

    def is_box(self, ast_node):
        """Composite element: "box" elements in SWC templates are
        blockquotes whose first child element is a heading"""
        if self.has_number_children(ast_node, minc=2) and \
                self.is_heading(ast_node['c'][0]):
            has_heading = True
        else:
            has_heading = False

        return self.is_block(ast_node) and has_heading
