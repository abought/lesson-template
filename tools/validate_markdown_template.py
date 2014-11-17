#! /usr/bin/env python

"""
Validate Software Carpentry lessons according to the markdown template specification described here:
http://software-carpentry.org/blog/2014/10/new-lesson-template-v2.html

Validates the presence of headings, as well as specific sub-nodes. Contains validators for several kinds of template.
"""

import argparse, json, logging, os, re, sys
import CommonMark


# Path to where markdown files are stored: relative to this file, should be ../pages
MARKDOWN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, "pages"))


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

    def has_section_heading(self, section_title, ast_node=None, limit=None):
        """Does the markdown contain (no more than x copies of) the specified heading text?"""
        if ast_node is None:
            ast_node = self.data

        num_nodes = len([n for n in self.get_section_headings(ast_node)
                         if n.strings[0] == section_title])

        if num_nodes == 0:
            logging.error("Document does not contain the specified heading: {0}".format(section_title))
        elif num_nodes > limit:
            logging.error("Document must not contain more than {0} copies of the heading {1}".format(limit, section_title))
        else:
            logging.info("Verified that document contains the specified heading: {0}".format(section_title))
        return (0 < num_nodes <= limit)

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

    def is_list(self, ast_node):
        """Is the node a list? (ordered or unordered)"""
        return ast_node.t == "List"

    def is_link(self, ast_node):
        """Is the node a link?"""
        return ast_node.t == "Link"


GLOBAL_CSS_CLASSES = []  # TODO: Write validator for CSS classes in document


class MarkdownValidator(object):
    """Base class for markdown validation; contains helper methods for working with the CommonMark ast,
    and basic validation skeleton to be extended for specific page types"""
    HEADINGS = []
    DOC_HEADERS = {}

    def __init__(self, filename=None, markdown=None):
        """Pass in the path to a filename containing markdown, OR a valid markdown string.
            The latter is useful for unit testing."""
        self.filename = filename
        if filename:
            with open(filename, 'rU') as f:
                self.markdown = f.read()
        else:
            self.markdown = markdown

        ast = self._parse_markdown(self.markdown)
        self.ast = CommonMarkHelper(ast)

    def _parse_markdown(self, markdown):
        parser = CommonMark.DocParser()
        ast = parser.parse(markdown)
        return ast

    def _validate_hrs(self):
        """Verify that the header section at top of document is bracketed by two horizontal rules"""
        # The header section should be bracketed by two HRs in the markup
        valid = True
        try:
            hr_nodes = [self.ast.children[0], self.ast.children[2]]
        except:
            logging.error("Document is too short, and must include header sections")
            return False

        for hr in hr_nodes:
            if not self.ast.is_hr(hr):
                logging.error("Expected horizontal rule (---) at line: {0}".format(hr.start_line))
                valid = False
        return valid

    def _validate_one_doc_header_row(self, text):
        """Validate a single row of the document header section"""
        label, content = text.split(":", 1)
        if label not in self.DOC_HEADERS:
            logging.warning("Unrecognized label in document header section: {0}".format(label))
            return False

        validation_function = self.DOC_HEADERS[label]
        validate_header = validation_function(text)
        if not validate_header:
            logging.error("Document header for label {0} does not follow expected format".format(label))
        return validate_header

    # Methods related to specific validation. Override in child classes with specific validators.
    def _validate_doc_headers(self):
        """Validate that the header of the document contains the specified sections with the expected contents
            Fail if any extraneous headers are present"""
        # Header section wrapped in hrs
        has_hrs = self._validate_hrs()

        # Labeled sections in the actual headers should match expected format
        ast_header_node = self.ast.children[1]
        checked_headers = [self._validate_one_doc_header_row(s)
                           for s in ast_header_node.strings]

        # Must not be missing headers, and must not have any extraneous header lines either
        only_headers = (len(ast_header_node.strings) == len(self.DOC_HEADERS.keys()))

        # Headings must appear in the order expected
        valid_order = self._validate_section_heading_order()

        return has_hrs and all(checked_headers) and only_headers and valid_order

    def _validate_section_heading_order(self, ast_node=None, headings=None):
        """Verify that section headings appear, and in the order expected"""
        if ast_node is None:
            ast_node = self.ast.data
            headings = self.HEADINGS

        heading_nodes = self.ast.get_section_headings(ast_node)
        heading_labels = [strip_attrs(n.strings[0]) for n in heading_nodes]

        # Check for missing and extra headings
        missing_headings = [expected_heading for expected_heading in headings
                            if expected_heading not in heading_labels]

        extra_headings = [found_heading for found_heading in heading_labels
                          if found_heading not in headings]

        for h in missing_headings:
            logging.error("Document does not contain the expected headings: {0}".format(h))

        for h in extra_headings:
            logging.warning("Document contains additional heading not specified in the template: {0}".format(h))

        # Check that the subset of headings in the template spec matches order in the document
        valid_order = True
        headings_overlap = [h for h in heading_labels if h in headings]
        if len(missing_headings) == 0 and headings_overlap != headings:
            valid_order = False
            logging.error("Document headings do not match the order specified by the template")

        return (len(missing_headings) == 0 and valid_order)

    def _validate_links(self):
        """Validate all links: assumption is that any local html file being linked was generated as part of the lesson
            - File links (.html) must have a markdown file in the expected location in the directory structure"""
        links = self.ast.find_links()

        valid = True
        for link in links:
            if re.match(r"^[\w,\s-]+\.(htm|html)$", link):  # This is a filename (not a web link), so confirm file exists
                expected_md_filename = os.path.splitext(link)[0] + os.extsep + "md"
                expected_md_path = os.path.join(MARKDOWN_DIR, expected_md_filename)
                if not os.path.isfile(expected_md_path):
                    logging.error("The document links to {0}, but could not find the expected markdown file {1}".format(
                        link, expected_md_path))
                    valid = False
        return valid

    def _run_tests(self):
        """Let user override the tests here, so that errors and exceptions can be captured by validate method"""
        tests = [self._validate_doc_headers(),
                 self._validate_section_heading_order(),
                 self._validate_links()]
        return all(tests)

    def validate(self):
        """Perform all required validations. Wrap in exception handler"""
        try:
            return self._run_tests()
        except IndexError:
            logging.error("Document is missing critical sections")
            return False


class HomePageValidator(MarkdownValidator):
    """Validate the contents of the homepage (index.md)"""
    HEADINGS = ['Topics',
                'Other Resources']

    DOC_HEADERS = {'layout': is_str,
                   'title': is_str,
                   'keywords': is_list}

    def _validate_intro_section(self):
        """Validate the content of a paragraph / intro section: Paragraph of text, followed by blockquote and list of prereqs"""
        intro_block = self.ast.children[3]
        intro_section = self.ast.is_paragraph(intro_block)
        if not intro_section:
            logging.error("Expected paragraph of introductory text at {0}".format(intro_block.start_line))

        # Validate the prerequisites block
        prereqs_block = self.ast.children[4]

        prereqs_indented = self.ast.is_heading(prereqs_block)
        prereqs_header = self.ast.has_section_heading("Prerequisites", ast_node=prereqs_block, limit=1)
        prereqs_has_content = self.ast.has_number_children(prereqs_block, minc=2)  # Title and at least some content

        prereqs_tests = all([prereqs_indented, prereqs_header, prereqs_has_content])

        if not prereqs_tests:
            logging.error("Intro section should contain a blockquoted section titled 'Prerequisites', which should not be empty, at line {0}".format(prereqs_block.start_line))

        return intro_section and prereqs_tests

    def _run_tests(self):
        tests = [self._validate_intro_section()]
        parent_tests = super(HomePageValidator, self)._run_tests()
        return all(tests) and parent_tests


class TopicPageValidator(MarkdownValidator):
    """Validate the markdown contents of a topic page, eg 01-topicname.md"""
    DOC_HEADERS = {"layout": is_str,
                   "title": is_str,
                   "minutes": is_numeric}

    # TODO: Write validator for, eg, challenge section
    def _validate_learning_objective(self):
        learn_node = self.ast.children[3]
        has_heading = self.ast.has_section_heading("Learning Objectives", ast_node=learn_node, limit=1)
        return has_heading

    def _validate_has_no_headings(self):
        """The top-level document has no headings indicating subtopics. The only valid subheadings are nested in blockquote elements"""
        heading_nodes = self.ast.get_section_headings()
        if len(heading_nodes) == 0:
            return True

        logging.error("The topic page should not have sub-headings outside of special blocks. If a topic needs sub-headings, it should be broken into multiple topics.")
        for n in heading_nodes:
            logging.warning("The following sub-heading should be removed: {}".format(n.strings[0]))
        return False

    def _run_tests(self):
        tests = [self._validate_has_no_headings(),
                 self._validate_learning_objective()]
        parent_tests = super(TopicPageValidator, self)._run_tests()
        return all(tests) and parent_tests


class IntroPageValidator(MarkdownValidator):
    pass


class ReferencePageValidator(MarkdownValidator):
    pass


class InstructorPageValidator(MarkdownValidator):
    pass


# Associate lesson template names with validators. Master list of templates recognized by CLI.
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
    """Called by argparse to handle one single file"""
    if validate_single(parsed_args_obj.file, parsed_args_obj.template):
        logging.info("File {} successfully passed validation".format(parsed_args_obj.file))
    else:
        logging.info("File {} failed validation: see error log for details".format(parsed_args_obj.file))
        sys.exit(1)


def _cmd_validate_batch(parsed_arg_obj):
    """Called by argparse to handle a batch of files"""
    # TODO: Implement
    raise NotImplementedError


def start_logging():
    """Start logging"""
    # TODO: Allow results to be captured in text files by adding a second logger
    # TODO: Errors (warning and above) should be sent to stderr
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

