#! /usr/bin/env python

"""
Validate Software Carpentry lessons
according to the Markdown template specification described here:
http://software-carpentry.org/blog/2014/10/new-lesson-template-v2.html

Validates the presence of headings, as well as specific sub-nodes.
Contains validators for several kinds of template.

This is a command line script
that can run on either a single file, or a batch of files.
Call at command line with flag -h to see options
"""
from __future__ import print_function
import argparse, glob, logging, os, re, sys


try:
    import CommonMark
except ImportError:
    ERROR_MESSAGE = """This program requires the CommonMark python package.
Install using

    # pip install commonmark

or

    # easy_install commonmark
"""
    print(ERROR_MESSAGE)
    sys.exit(1)

import validation_helpers as vh


class MarkdownValidator(object):
    """Base class for Markdown validation

    Contains basic validation skeleton to be extended for specific page types"""
    HEADINGS = []  # List of strings containing expected heading text
    DOC_HEADERS = {}  # Rows in header section (first few lines of document).

    def __init__(self, filename=None, markdown=None):
        """Pass is is a valid Markdown.

        It can pass either if
        the path to a file containing Markdown
        OR is a valid Markdown string.
        The latter is useful for unit testing."""
        self.filename = filename

        if filename:
            # When checking links,
            # expect Markdown files to be in same directory as the input file
            self.markdown_dir = os.path.dirname(filename)
            with open(filename, 'rU') as f:
                self.markdown = f.read()
        else:
            # If not given a file path,
            # link checker looks for Markdown in ../pages
            # relative to where the script is located
            self.markdown_dir = os.path.abspath(
                os.path.join(os.path.dirname(__file__), os.pardir, "pages"))
            self.markdown = markdown

        ast = self._parse_markdown(self.markdown)
        self.ast = vh.CommonMarkHelper(ast)

    def _parse_markdown(self, markdown):
        parser = CommonMark.DocParser()
        ast = parser.parse(markdown)
        return ast

    def _validate_hrs(self):
        """Validate header

        Verify that the header section at top of document
        is bracketed by two horizontal rules"""
        valid = True
        try:
            hr_nodes = [self.ast.children[0], self.ast.children[2]]
        except:
            logging.error("Document must include header sections")
            return False

        for hr in hr_nodes:
            if not self.ast.is_hr(hr):
                logging.error("Expected --- at line: {0}".format(hr.start_line))
                valid = False
        return valid

    def _validate_one_doc_header_row(self, text):
        """Validate a single row of the document header section"""
        label, content = text.split(":", 1)
        if label not in self.DOC_HEADERS:
            logging.warning("Unrecognized label in header: {0}".format(label))
            return False

        validation_function = self.DOC_HEADERS[label]
        validate_header = validation_function(content)
        if not validate_header:
            logging.error(
                "Document header field for label {0} " \
                "does not follow expected format".format(label))
        return validate_header

    # Methods related to specific validation.
    # Override in child classes with specific validators.
    def _validate_doc_headers(self):
        """Validate header

        Pass if the header of the document contains
        the specified sections with the expected contents
        and fail otherwise."""
        # Header section wrapped in hrs
        has_hrs = self._validate_hrs()

        # Labeled sections in the actual headers should match expected format
        ast_header_node = self.ast.children[1]
        checked_headers = [self._validate_one_doc_header_row(s)
                           for s in ast_header_node.strings]

        # Must not be missing headers,
        # and must not have any extraneous header lines either
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
        heading_labels = [vh.strip_attrs(n.strings[0]) for n in heading_nodes]

        # Check for missing and extra headings
        missing_headings = [expected_heading for expected_heading in headings
                            if expected_heading not in heading_labels]

        extra_headings = [found_heading for found_heading in heading_labels
                          if found_heading not in headings]

        for h in missing_headings:
            logging.error("Document does not contain the headings: {0}".format(h))

        for h in extra_headings:
            logging.warning("Document contains additional headings: {0}".format(h))

        # Check that the subset of headings
        # in the template spec matches order in the document
        valid_order = True
        headings_overlap = [h for h in heading_labels if h in headings]
        if len(missing_headings) == 0 and headings_overlap != headings:
            valid_order = False
            logging.error(
                "Document headings do not match " \
                "the order specified by the template")

        return (len(missing_headings) == 0 and valid_order)

    def _validate_links(self):
        """Validate all links

        Any local html file being linked was generated as part of the lesson
        and, because of this,
        file links (.html) must have a Markdown file
        in the expected location in the directory structure"""
        links = self.ast.find_links()

        valid = True
        for link in links:
            if re.match(r"^[\w,\s-]+\.(htm|html)$", link):
                # This is a filename (not a web link), so confirm file exists
                expected_md_filename = os.path.splitext(link)[0] + os.extsep + "md"
                expected_md_path = os.path.join(self.markdown_dir, expected_md_filename)
                if not os.path.isfile(expected_md_path):
                    logging.error(
                        "The document links to {0}, " \
                        "but could not find the expected Markdown file {1}".format(
                            link, expected_md_path))
                    valid = False
        return valid

    def _run_tests(self):
        """Let user override the tests

        This enables that errors and exceptions
        can be captured by validate method"""
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


class IndexPageValidator(MarkdownValidator):
    """Validate the contents of the homepage (index.md)"""
    HEADINGS = ['Topics',
                'Other Resources']

    DOC_HEADERS = {'layout': vh.is_str,
                   'title': vh.is_str}

    def _validate_intro_section(self):
        """Validate the intro

        It must be a paragraph of text,
        followed by blockquote and list of prereqs"""
        intro_block = self.ast.children[3]
        intro_section = self.ast.is_paragraph(intro_block)
        if not intro_section:
            logging.error(
                "Expected paragraph of introductory text at {0}".format(
                    intro_block.start_line))

        # Validate the prerequisites block
        prereqs_block = self.ast.get_block_titled("Prerequisites")
        if prereqs_block:
            # Confirmed it's blockquoted and has the heading; now check contents
            prereqs_tests = self.ast.has_number_children(prereqs_block[0], minc=2)
        else:
            prereqs_tests = False

        if prereqs_tests is False:
            logging.error(
                "Intro section should contain a blockquoted section " \
                "titled 'Prerequisites', which should not be empty")
        return intro_section and prereqs_tests

    def _run_tests(self):
        tests = [self._validate_intro_section()]
        parent_tests = super(IndexPageValidator, self)._run_tests()
        return all(tests) and parent_tests


class TopicPageValidator(MarkdownValidator):
    """Validate the Markdown contents of a topic page, eg 01-topicname.md"""
    DOC_HEADERS = {"layout": vh.is_str,
                   "title": vh.is_str,
                   "subtitle": vh.is_str,
                   "minutes": vh.is_numeric}

    # TODO: Write validator for, eg, challenge section
    def _validate_learning_objective(self):
        learn_node = self.ast.get_block_titled("Learning Objectives")
        if learn_node:
            node_tests = self.ast.has_number_children(learn_node[0], minc=2)
        else:
            node_tests = False

        if node_tests is False:
            logging.error(
                "Topic should contain a blockquoted section " \
                "titled 'Learning Objectives', which should not be empty")

        return node_tests

    def _validate_has_no_headings(self):
        """Check headings

        The top-level document has no headings indicating subtopics.
        The only valid subheadings are nested in blockquote elements"""
        heading_nodes = self.ast.get_section_headings()
        if len(heading_nodes) == 0:
            return True

        logging.error(
            "The topic page should not have sub-headings " \
            "outside of special blocks. " \
            "If a topic needs sub-headings, " \
            "it should be broken into multiple topics.")
        for n in heading_nodes:
            logging.warning(
                "The following sub-heading should be removed: {}".format(
                    n.strings[0]))
        return False

    def _run_tests(self):
        tests = [self._validate_has_no_headings(),
                 self._validate_learning_objective()]
        parent_tests = super(TopicPageValidator, self)._run_tests()
        return all(tests) and parent_tests


class MotivationPageValidator(MarkdownValidator):
    """Validate motivation.md"""
    DOC_HEADERS = {"layout": vh.is_str,
                   "title": vh.is_str}
    # TODO: Find out what validation is needed.
    # This file might be a mix of reveal.js (HTML) + markdown


class ReferencePageValidator(MarkdownValidator):
    """Validate reference.md"""
    DOC_HEADERS = {"layout": vh.is_str,
                   "title": vh.is_str,
                   "subtitle": vh.is_str}
    HEADINGS = ["Glossary"]


class InstructorPageValidator(MarkdownValidator):
    """Simple validator for Instructor's Guide- instructors.md"""
    HEADINGS = ["Legend", "Overall"]
    DOC_HEADERS = {"layout": vh.is_str,
                   "title": vh.is_str,
                   "subtitle": vh.is_str}


# Associate lesson template names with validators.
# Master list of templates recognized by CLI.
# Dict of {name: (Validator, filename_pattern)}
LESSON_TEMPLATES = {"index": (IndexPageValidator, "^index"),
                    "topic": (TopicPageValidator, "^[0-9]{2}-.*"),
                    "motivation": (MotivationPageValidator, "^motivation"),
                    "reference": (ReferencePageValidator, "^reference"),
                    "instructor": (InstructorPageValidator, "^instructors")}


def identify_template(filepath):
    """Identify template

    Given the path to a single file,
    identify the appropriate template to use"""
    for template_name, (validator, pattern) in LESSON_TEMPLATES.items():
        if re.search(pattern, os.path.basename(filepath)):
            return template_name

    return None


def validate_single(filepath, template=None):
    """Validate a single Markdown file based on a specified template"""
    template = template or identify_template(filepath)
    if template is None:
        logging.error(
            "Validation failed: " \
            "Could not automatically identify correct template " \
            "to use with {}".format(filepath))
        return False

    logging.info(
        "Beginning validation of {} " \
        "using template {}".format(filepath, template))
    validator = LESSON_TEMPLATES[template][0]
    validate_file = validator(filepath)

    res = validate_file.validate()
    if res is True:
        logging.info("File {} successfully passed validation".format(filepath))
    else:
        logging.info("File {} failed validation: see error log for details".format(filepath))

    return res


def validate_folder(path, template=None):
    """Validate an entire folder of files"""
    search_str = os.path.join(path, "*.md")  # Validate files with .md extension
    filename_list = glob.glob(search_str)

    if not filename_list:
        logging.error(
            "No Markdown files were found " \
            "in specified directory {}".format(path))
        return False

    all_valid = True
    for fn in filename_list:
        res = validate_single(fn, template=template)
        all_valid = all_valid and res
    return all_valid


def start_logging():
    """Start logging

    Can be modified to control
    what types of messages are written out, and where"""
    logging.basicConfig(stream=sys.stdout, level=logging.INFO)


def command_line():
    """Handle arguments passed in via the command line"""
    parser = argparse.ArgumentParser()
    parser.add_argument("file_or_path",
                        nargs="*",
                        default=[os.getcwd()],
                        help="The individual pathname")

    parser.add_argument('-t', '--template',
                        choices=LESSON_TEMPLATES.keys(),
                        help="The type of lesson template to apply to all file(s). If not specified, will auto-identify template.")

    return parser.parse_args()


if __name__ == "__main__":
    start_logging()
    parsed_args = command_line()

    template = parsed_args.template

    all_valid = True
    for e in parsed_args.file_or_path:
        if os.path.isdir(e):
            res = validate_folder(e, template=template)
        elif os.path.isfile(e):
            res = validate_single(e, template=template)
        else:
            res = False
            logging.error(
                "The specified file or folder {} does not exist; " \
                "could not perform validation".format(e))

        all_valid = all_valid and res

    if all_valid is True:
        logging.info("All Markdown files successfully passed validation.")
    else:
        logging.warning(
            "Some errors were encountered during validation. " \
            "See log for details.")
        sys.exit(1)


    #### Sample of how validator is used directly
    # validator = HomePageValidator('../index.md')
    # print validator.validate()
