#! /usr/bin/env python

import argparse, logging, sys
import CommonMark


class MarkdownValidator(object):
    """Base class for markdown validation; contains helper methods for working with the CommonMark ast,
    and basic validation skeleton to be extended for specific page types"""
    HEADINGS = []  # Tuples of (heading_text, count). Use None if there is no limit on how many times the heading can appear.

    def __init__(self, filename):
        with open(filename, 'rU') as f:
            self.markdown = f.read()

        self.ast = self._parse_markdown()

    def _parse_markdown(self):
        parser = CommonMark.DocParser()
        ast = parser.parse(self.markdown)
        return ast

    ### Helper methods for working with CommonMark ast
    def _has_section_heading(self, section_title, ast_node=None, limit=None):
        """Does the markdown contain (no more than x copies of) the specified heading?"""
        if ast_node is None:
            ast_node = self.ast
        if limit is None:
            limit = sys.maxint

        nodes = [n for n in ast_node.children if n.t == "ATXHeader" and section_title in n.strings]
        num_nodes = len(nodes)
        if num_nodes == 0:
            logging.error("Document does not contain the specified heading: {0}".format(section_title))
            print 1
        elif num_nodes > limit:
            logging.error("Document must not contain more than {0} copies of the heading {1}".format(limit, section_title))
            print 2
        else:
            logging.info("Verified that document contains the specified heading: {0}".format(section_title))
            print 3
        return (0 < num_nodes <= limit)

    def _get_child_type(self, ast_node, child_type):
        """Get all children of a given node, if they are of the specified type"""
        return [n for n in ast_node.children if n.t == child_type]

    def _has_number_children(self, ast_node, exact=None, minc=0, maxc=sys.maxint):
        """Does the specified node (such as a bulleted list) have the expected number of children?"""

        if exact:  # If specified, must have exactly this number of children
            minc = maxc = exact

        return (minc <= len(ast_node.children) <= maxc)

    # Perform validation. Override in child classes with specific validators.
    def _validate_section_headings(self):
        """Verify that the top level document contains all specified headings. (don't just stop when one fails)"""
        tests = [self._has_section_heading(heading_text, limit=max_count)
                 for heading_text, max_count in self.HEADINGS]
        return all(tests)

    def _validate_doc_headers(self):
        """Validate that the header of the document contains the specified sections with the expected contents"""
        return True

    def validate(self):
        """Perform all required validations"""
        tests = [self._validate_section_headings(),
                 self._validate_doc_headers()]
        return all(tests)


class HomePageValidator(MarkdownValidator):
    """Validate the contents of the homepage (index.md)"""
    HEADINGS = [('Topics', 1),
                ('Other Resources', 1)]
    # TODO: Prerequisites should be a subheading under the paragraph of introductory material section. How to handle?
    # ('Prerequisites', 1),

    def _validate_intro_section(self):
        """Validate the content of a paragraph / intro section"""
        intro_section = self.ast.children[3]
        print vars(intro_section)
        # FIXME: Prereqs is inside a block element
        return self._has_section_heading("Prerequisites", ast_node=intro_section, limit=1)

    def validate(self):
        tests = [self._validate_intro_section()]
        return all(tests) and super(HomePageValidator, self).validate()


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