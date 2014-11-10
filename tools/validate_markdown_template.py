#! /usr/bin/env python

import argparse, json, logging, sys
import CommonMark


#### Common validation functions ###
def is_list(text):
    """Validate whether the provided string can be converted to a valid python list"""
    text = text.strip()
    try:
        text_as_list = json.loads(text)
    except:
        return False

    return isinstance(text_as_list, list)


def is_str(text):
    """Validate whether the input is a non-blank python string"""
    return isinstance(text, basestring) and len(text) > 0


class CommonMarkHelper(object):
    """Basic helper functions for working with the internal abstract syntax tree produced by CommonMark parser"""
    def __init__(self, ast):
        self.data = ast
        self.children = self.data.children

    def has_section_heading(self, section_title, ast_node=None, limit=None):
        """Does the markdown contain (no more than x copies of) the specified heading text?"""
        if ast_node is None:
            ast_node = self.data  # If no level of the document is specified, search top-level headings
        if limit is None:
            limit = sys.maxint

        nodes = [n for n in ast_node.children if n.t == "ATXHeader" and section_title in n.strings]
        num_nodes = len(nodes)
        if num_nodes == 0:
            logging.error("Document does not contain the specified heading: {0}".format(section_title))
        elif num_nodes > limit:
            logging.error("Document must not contain more than {0} copies of the heading {1}".format(limit, section_title))
        else:
            logging.info("Verified that document contains the specified heading: {0}".format(section_title))
        return (0 < num_nodes <= limit)

    def get_child_type(self, ast_node, child_type):
        """Get all children of a given node, if they are of the specified type"""
        return [n for n in ast_node.children if n.t == child_type]

    def has_number_children(self, ast_node, exact=None, minc=0, maxc=sys.maxint):
        """Does the specified node (such as a bulleted list) have the expected number of children?"""

        if exact:  # If specified, must have exactly this number of children
            minc = maxc = exact

        return (minc <= len(ast_node.children) <= maxc)

    def is_hr(self, ast_node):
        """Is the node a horizontal rule (hr)?"""
        return ast_node.t == 'HorizontalRule'

    def is_heading(self, ast_node):
        """Is the node a heading/ title?"""
        return ast_node.t == "ATXHeader"

    def is_paragraph(self, ast_node):
        """Is the node a paragraph?"""
        return ast_node.t == "Paragraph"


class MarkdownValidator(object):
    """Base class for markdown validation; contains helper methods for working with the CommonMark ast,
    and basic validation skeleton to be extended for specific page types"""
    # TODO: Change headings to dict
    HEADINGS = []  # Tuples of (heading_text, count). Use None if there is no limit on how many times the heading can appear.
    DOC_HEADERS = {}


    def __init__(self, filename):
        with open(filename, 'rU') as f:
            self.markdown = f.read()

        ast = self._parse_markdown()
        self.ast = CommonMarkHelper(ast)

    def _parse_markdown(self):
        parser = CommonMark.DocParser()
        ast = parser.parse(self.markdown)
        return ast

    def __validate_hrs(self):
        """Verify that the header section at top of document is bracketed by two horizontal rules"""
        # The header section should be bracketed by two HRs in the markup
        valid = True
        for hr in [self.ast.children[0], self.ast.children[2]]:
            if not self.ast.is_hr(hr):
                logging.error("Expected horizontal rule (---) at line: {0}".format(hr.start_line))
                valid = False
        return valid

    def __validate_one_doc_header_row(self, text):
        """Validate a single row of the document header section"""
        label, content = text.split(":", 1)
        if label not in self.DOC_HEADERS:
            logging.warning("Unrecognized label in document header section: {0}".format(label))
            return False

        validate_header = self.DOC_HEADERS[label]
        if not validate_header:
            logging.error("Document header for label {0} does not follow expected format".format(label))
        return validate_header

    # Methods related to specific validation. Override in child classes with specific validators.
    def _validate_doc_headers(self):
        """Validate that the header of the document contains the specified sections with the expected contents
            Fail if any extraneous headers are present"""
        # Header section wrapped in hrs
        has_hrs = self.__validate_hrs()

        # Labeled sections in the actual headers should match expected format
        ast_header_node = self.ast.children[1]
        checked_headers = [self.__validate_one_doc_header_row(s)
                           for s in ast_header_node.strings]

        # No extraneous headers
        only_headers = (len(ast_header_node.strings) == len(self.DOC_HEADERS.keys()))

        return has_hrs and all(checked_headers) and only_headers

    def _validate_section_headings(self):
        """Verify that the top level document contains all specified headings. (don't just stop when one fails)"""
        tests = [self.ast.has_section_heading(heading_text, limit=max_count)
                 for heading_text, max_count in self.HEADINGS]
        return all(tests)

    def validate(self):
        """Perform all required validations"""
        tests = [self._validate_section_headings(),
                 self._validate_doc_headers()]
        return all(tests)


class HomePageValidator(MarkdownValidator):
    """Validate the contents of the homepage (index.md)"""
    HEADINGS = [('Topics', 1),
                ('Other Resources', 1)]

    DOC_HEADERS = {'layout': is_str,
                   'title': is_str,
                   'keywords': is_list}

    def _validate_intro_section(self):
        """Validate the content of a paragraph / intro section"""
        intro_section = self.ast.children[3]
        # FIXME: Prereqs is inside a block element
        return self.ast.has_section_heading("Prerequisites", ast_node=intro_section, limit=1)

    def validate(self):
        tests = [self._validate_intro_section()]
        parent_tests = super(HomePageValidator, self).validate()
        return all(tests) and parent_tests


class TopicPageValidator(MarkdownValidator):
    """Validate the markdown contents of a topic page"""
    pass


class IntroPageValidator(MarkdownValidator):
    pass


class ReferencePageValidator(MarkdownValidator):
    pass


class InstructorPageValidator(MarkdownValidator):
    pass


# Associate lesson template names with parsers
LESSON_TEMPLATES = {"home": HomePageValidator,
                    "topic": TopicPageValidator,
                    "intro": IntroPageValidator,
                    "reference": ReferencePageValidator,
                    "instructor": InstructorPageValidator}


def validate_single(filepath, template):
    """Validate a single markdown file based on a specified template"""
    validator = LESSON_TEMPLATES[template]
    validate_file = validator(filepath)
    return validate_file.validate()


def _cmd_validate_single(parsed_args_obj):
    """Called by argparse"""
    if validate_single(parsed_args.file, parsed_args.template):
        logging.info("File {} successfully passed validation".format(parsed_args.file))
    else:
        logging.info("File {} failed validation: see error log for details".format(parsed_args.file))
        sys.exit(1)


def _cmd_validate_batch(parsed_arg_obj):
    """Called by argparse to handle a batch of files"""
    # TODO: Implement
    raise NotImplementedError


def start_logging():
    """Start logging"""
    # TODO: Allow results to be captured in text files by adding a second logger
    logging.basicConfig(stream=sys.stdout, level=logging.INFO)


def command_line():
    """Handle arguments passed in via the command line"""
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()

    # Provide modes to validate a single file vs multiple files
    single_file_parser = subparsers.add_parser("single", help="Validate one single markdown file")
    single_file_parser.add_argument("file", type=str,
                                    help="The path to the file to validate")
    single_file_parser.add_argument("template",
                                    choices=LESSON_TEMPLATES.keys(),
                                    help="The kind of lesson template to apply")
    single_file_parser.set_defaults(func=_cmd_validate_single)

    # TODO: Implement
    batch_parser = subparsers.add_parser("batch", help="Validate all files in the project")
    batch_parser.set_defaults(func=_cmd_validate_batch)

    return parser.parse_args()


if __name__ == "__main__":
    start_logging()
    parsed_args = command_line()
    parsed_args.func(parsed_args)

    #index_valid = HomePageValidator("../index.md")
    #print index_valid.validate()