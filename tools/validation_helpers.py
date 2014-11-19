#! /usr/bin/env python


import json, logging, re, sys


#### Common validation functions ###
def is_list(text):
    """Validate whether the provided string can be converted to a valid python list"""
    text = text.strip()
    try:
        text_as_list = json.loads(text)
    except ValueError:
        logging.debug("Could not convert string to python object: {0}".format(text))
        return False

    return isinstance(text_as_list, list)


def is_str(text):
    """Validate whether the input is a non-blank python string"""
    return isinstance(text, basestring) and len(text) > 0


def is_numeric(text):
    """Validate whether the string represents a number (including unicode)"""
    try:
        float(text)
        return True
    except ValueError:
        return False


#### Text cleanup functions, pre-validation
def strip_attrs(s):
    """Strip attributes of the form {.name} from a markdown title string"""
    return re.sub(r"\s\{\..*?\}", "", s)


def get_css_class(s):
    """Return any and all CSS classes: present when a line is suffixed by {.classname}
    Returns empty list when """
    return re.findall("\{\.(.*?)\}", s)


### Helper objects
class CommonMarkHelper(object):
    """Basic helper functions for working with the internal abstract syntax tree produced by CommonMark parser"""
    def __init__(self, ast):
        self.data = ast
        self.children = self.data.children

    def get_block_titled(self, title, ast_node=None):
        """Examine children. Return all children of the given node that:
        a) are blockquoted elements, and
        b) contain a heading with the specified text.
        For example, this can be used to find the indented "Prerequisites" section in index.md

        Returns empty list if no appropriate node is found"""
        if ast_node is None:
            ast_node = self.data
        return [n for n in ast_node.children
                if self.is_block(n) and self.has_section_heading(title, ast_node=n, show_msg=False)]

    def get_section_headings(self, ast_node=None):
        """Returns a list of ast nodes that are headings"""
        if ast_node is None:
            ast_node = self.data
        return [n for n in ast_node.children if self.is_heading(n)]

    def find_links(self, ast_node=None):
        """Recursive function that locates all hyperlinks under the specified node.
        Returns a list specifying the destination of each link"""
        ast_node = ast_node or self.data

        # Links can be hiding in this node in two ways
        links = [n.destination
                 for n in ast_node.inline_content if self.is_link(n)]

        if self.is_link(ast_node):
            links.append(ast_node.destination)

        # Also look for links in sub-nodes
        for n in ast_node.children:
            links.extend(self.find_links(n))

        return links

    def has_section_heading(self, section_title, ast_node=None, limit=sys.maxint, show_msg=True):
        """Does the markdown contain (no more than x copies of) the specified heading text?
        Automatically strips off any CSS attributes when looking for the section title"""
        if ast_node is None:
            ast_node = self.data

        num_nodes = len([n for n in self.get_section_headings(ast_node)
                         if strip_attrs(n.strings[0]) == section_title])

        # Log an error message, unless explicitly told not to (eg if used as a helper method in a larger test)
        if show_msg and num_nodes == 0:
            logging.error("Document does not contain the specified heading: {0}".format(section_title))
        elif show_msg and num_nodes > limit:
            logging.error("Document must not contain more than {0} copies of the heading {1}".format(limit, section_title or 0))
        elif show_msg:
            logging.info("Verified that document contains the specified heading: {0}".format(section_title))
        return (0 < num_nodes <= limit)

    def has_number_children(self, ast_node, exact=None, minc=0, maxc=sys.maxint):
        """Does the specified node (such as a bulleted list) have the expected number of children?"""

        if exact:  # If specified, must have exactly this number of children
            minc = maxc = exact

        return (minc <= len(ast_node.children) <= maxc)

    # Helpers, in case the evolving CommonMark spec changes the names of nodes
    def is_hr(self, ast_node):
        """Is the node a horizontal rule (hr)?"""
        return ast_node.t == 'HorizontalRule'

    def is_heading(self, ast_node):
        """Is the node a heading/ title?"""
        return ast_node.t == "ATXHeader"

    def is_paragraph(self, ast_node):
        """Is the node a paragraph?"""
        return ast_node.t == "Paragraph"

    def is_list(self, ast_node):
        """Is the node a list? (ordered or unordered)"""
        return ast_node.t == "List"

    def is_link(self, ast_node):
        """Is the node a link?"""
        return ast_node.t == "Link"

    def is_block(self, ast_node):
        """Is the node a BlockQuoted element?"""
        return ast_node.t == "BlockQuote"
