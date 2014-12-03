#! /usr/bin/env python

"""
Validate Software Carpentry lessons
according to the Markdown template specification described here:
http://software-carpentry.org/blog/2014/10/new-lesson-template-v2.html

Validates the presence of headings, as well as specific sub-nodes.
Contains validators for several kinds of template.

Call at command line with flag -h to see options and usage instructions.
"""
from __future__ import print_function
import argparse, glob, hashlib, logging, os, re, sys


try:
    # Code tested with CommonMark version 0.5.4; API may change
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

    Contains basic validation skeleton to be extended for specific page types
    """
    HEADINGS = []  # List of strings containing expected heading text
    WARN_ON_EXTRA_HEADINGS = True  # Warn when other headings are present?

    DOC_HEADERS = {}  # Rows in header section (first few lines of document).

    def __init__(self, filename=None, markdown=None):
        """Perform validation on a Markdown document.

        Validator accepts either the path to a file containing Markdown,
        OR a valid Markdown string. The latter is useful for unit testing."""
        self.filename = filename

        if filename:
            # Expect Markdown files to be in same directory as the input file
            self.markdown_dir = os.path.dirname(filename)
            with open(filename, 'rU') as f:
                self.markdown = f.read()
        else:
            # Look for linked content in ../pages (relative to this file)
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
        except IndexError:
            logging.error("Document must include header sections")
            return False

        for hr in hr_nodes:
            if not self.ast.is_hr(hr):
                logging.error("Expected --- at line: {0}".format(
                    hr.start_line))
                valid = False
        return valid

    def _validate_one_doc_header_row(self, text):
        """Validate a single row of the document header section"""
        label, content = text.split(":", 1)
        if label not in self.DOC_HEADERS:
            logging.warning("Unrecognized label in header section: {0}".format(
                label))
            return False

        validation_function = self.DOC_HEADERS[label]
        validate_header = validation_function(content)
        if not validate_header:
            logging.error(
                "Document header field for label {0} "
                "does not follow expected format".format(label))
        return validate_header

    # Methods related to specific validation. Can override specific tests.
    def _validate_doc_headers(self):
        """Validate the document header section.

        Pass only if the header of the document contains the specified
            sections with the expected contents"""

        # Header section should be wrapped in hrs
        has_hrs = self._validate_hrs()

        # Labeled sections in the actual headers should match expected format
        header_node = self.ast.children[1]
        test_headers = [self._validate_one_doc_header_row(s)
                        for s in header_node.strings]

        # Must have all expected header lines, and no others.
        only_headers = (len(header_node.strings) == len(self.DOC_HEADERS))

        # Headings must appear in the order expected
        valid_order = self._validate_section_heading_order()

        return has_hrs and all(test_headers) and only_headers and valid_order

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
            logging.error("Document is missing expected heading: {0}".format(
                h))

        if self.WARN_ON_EXTRA_HEADINGS is True:
            for h in extra_headings:
                logging.error("Document contains heading "
                              "not specified in the template: {0}".format(h))
            no_extra = (len(extra_headings) == 0)
        else:
            no_extra = False

        # Check that the subset of headings
        # in the template spec matches order in the document
        valid_order = True
        headings_overlap = [h for h in heading_labels if h in headings]
        if len(missing_headings) == 0 and headings_overlap != headings:
            valid_order = False
            logging.error(
                "Document headings do not match "
                "the order specified by the template")

        return (len(missing_headings) == 0 and valid_order and no_extra)

    def _validate_one_link(self, link_node):
        """Logic to validate a single link

        Any local html file being linked was generated as part of the lesson.
        Therefore, file links (.html) must have a Markdown file
            in the expected folder.

        The title of the linked Markdown document should match the link text.
        """

        dest, link_text = self.ast.get_link_info(link_node)

        if re.match(r"^[\w,\s-]+\.(htm|html)$", dest):
            # This is a filename (not a web link), so confirm file exists
            expected_md_fn = os.path.splitext(dest)[0] + os.extsep + "md"
            expected_md_path = os.path.join(self.markdown_dir,
                                            expected_md_fn)
            if not os.path.isfile(expected_md_path):
                logging.error("The document links to {0}, but could not find "
                              "the expected markdown file {1}".format(
                                  dest, expected_md_path))
                return False

            # If file exists, parse and validate link text = node title
            with open(expected_md_path, 'rU') as link_dest_file:
                dest_contents = link_dest_file.read()

            dest_ast = self._parse_markdown(dest_contents)
            dest_ast = vh.CommonMarkHelper(dest_ast)
            dest_page_title = dest_ast.get_doc_header_title()

            if dest_page_title != link_text:
                logging.error("The linked page {0} exists, but "
                              "the link text '{1}' does not match the "
                              "title of that page, '{2}'.".format(
                                  dest, link_text, dest_page_title))
                return False

        return True

    def _validate_links(self):
        """Validate all links in the document"""
        links = self.ast.find_links()

        valid = True
        for link_node in links:
            res = self._validate_one_link(link_node)
            valid = valid and res
        return valid

    def _run_tests(self):
        """
        Let user override the list of tests to be performed.

        Error trapping is handled by the validate() wrapper method.
        """
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
        """Validate the intro section

        It must be a paragraph, followed by blockquoted list of prereqs"""
        intro_block = self.ast.children[3]
        intro_section = self.ast.is_paragraph(intro_block)
        if not intro_section:
            logging.error(
                "Expected paragraph of introductory text at {0}".format(
                    intro_block.start_line))

        # Validate the prerequisites block
        prereqs_block = self.ast.get_block_titled("Prerequisites")
        if prereqs_block:
            # Found the expected block; now check contents
            prereqs_tests = self.ast.has_number_children(prereqs_block[0],
                                                         minc=2)
        else:
            prereqs_tests = False

        if prereqs_tests is False:
            logging.error(
                "Intro section should contain a blockquoted section "
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
            # In addition to title, the node must have some content
            node_tests = self.ast.has_number_children(learn_node[0], minc=2)
        else:
            node_tests = False

        if node_tests is False:
            logging.error(
                "Topic should contain a blockquoted section "
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
            "The topic page should not have sub-headings "
            "outside of special blocks. "
            "If a topic needs sub-headings, "
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
    # TODO: How to validate? May be a mix of reveal.js (HTML) + markdown.


class ReferencePageValidator(MarkdownValidator):
    """Validate reference.md"""
    DOC_HEADERS = {"layout": vh.is_str,
                   "title": vh.is_str,
                   "subtitle": vh.is_str}
    HEADINGS = ["Glossary"]


class InstructorPageValidator(MarkdownValidator):
    """Simple validator for Instructor's Guide- instructors.md"""
    HEADINGS = ["Legend", "Overall"]
    WARN_ON_EXTRA_HEADINGS = False
    DOC_HEADERS = {"layout": vh.is_str,
                   "title": vh.is_str,
                   "subtitle": vh.is_str}


class LicensePageValidator(MarkdownValidator):
    """Validate LICENSE.md: user should not edit this file"""
    def _run_tests(self):
        """Skip the base tests; just check md5 hash"""
        # TODO: This hash is specific to the license for english-language repo
        expected_hash = '258aa6822fa77f7c49c37c3759017891'
        m = hashlib.md5()
        try:
            m.update(self.markdown)
        except TypeError:
            # Workaround for hashing in python3
            m.update(self.markdown.encode('utf-8'))

        if m.hexdigest() == expected_hash:
            return True
        else:
            logging.error("The provided license file should not be modified.")
            return False


class DiscussionPageValidator(MarkdownValidator):
    """
    Validate the discussion page (discussion.md).
    Most of the content is free-form.
    """
    DOC_HEADERS = {"layout": vh.is_str,
                   "title": vh.is_str,
                   "subtitle": vh.is_str}


# Associate lesson template names with validators. This list used by CLI.
#   Dict of {name: (Validator, filename_pattern)}
LESSON_TEMPLATES = {"index": (IndexPageValidator, "^index"),
                    "topic": (TopicPageValidator, "^[0-9]{2}-.*"),
                    "motivation": (MotivationPageValidator, "^motivation"),
                    "reference": (ReferencePageValidator, "^reference"),
                    "instructor": (InstructorPageValidator, "^instructors"),
                    "license": (LicensePageValidator, "^LICENSE"),
                    "discussion": (DiscussionPageValidator, "^discussion")}


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
            "Validation failed: "
            "Could not automatically identify correct template "
            "to use with {}".format(filepath))
        return False

    logging.info(
        "Beginning validation of {} using template {}".format(
            filepath, template))
    validator = LESSON_TEMPLATES[template][0]
    validate_file = validator(filepath)

    res = validate_file.validate()
    if res is True:
        logging.info("File {} successfully passed validation".format(filepath))
    else:
        logging.info("File {} failed validation: "
                     "see error log for details".format(filepath))

    return res


def validate_folder(path, template=None):
    """Validate an entire folder of files"""
    search_str = os.path.join(path, "*.md")  # Find files based on extension
    filename_list = glob.glob(search_str)

    if not filename_list:
        logging.error(
            "No Markdown files were found "
            "in specified directory {}".format(path))
        return False

    all_valid = True
    for fn in filename_list:
        res = validate_single(fn, template=template)
        all_valid = all_valid and res
    return all_valid


def start_logging():
    """Initialize logging and print messages to console."""
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
                        help="The type of template to apply to all file(s). "
                             "If not specified, will auto-identify template.")

    return parser.parse_args()


def main(parsed_args_obj):
    template = parsed_args_obj.template

    all_valid = True
    for e in parsed_args_obj.file_or_path:
        if os.path.isdir(e):
            res = validate_folder(e, template=template)
        elif os.path.isfile(e):
            res = validate_single(e, template=template)
        else:
            res = False
            logging.error(
                "The specified file or folder {} does not exist; "
                "could not perform validation".format(e))

        all_valid = all_valid and res

    if all_valid is True:
        logging.info("All Markdown files successfully passed validation.")
        sys.exit(0)
    else:
        logging.warning(
            "Some errors were encountered during validation. "
            "See log for details.")
        sys.exit(1)


if __name__ == "__main__":
    start_logging()
    parsed_args = command_line()
    main(parsed_args)

    #### Sample of how validator is used directly
    # validator = HomePageValidator('../index.md')
    # print validator.validate()
