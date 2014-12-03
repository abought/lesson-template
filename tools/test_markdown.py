#! /usr/bin/env python

import imp, os, unittest
check = imp.load_source("check",  # Import non-.py file
                        os.path.join(os.path.dirname(__file__), "check"))

check.start_logging()  # Make log messages visible to help audit test failures


class BaseTemplateTest(unittest.TestCase):
    """Common methods for testing template validators"""
    SAMPLE_FILE = "" # Path to a file that should pass all tests
    VALIDATOR = check.MarkdownValidator

    def setUp(self):
        self.sample_validator = self.VALIDATOR(self.SAMPLE_FILE)

    def _create_validator(self, markdown):
        """Create validator object from markdown string; useful for failures"""
        return self.VALIDATOR(markdown=markdown)


class TestAstHelpers(BaseTemplateTest):
    SAMPLE_FILE = '../pages/index.md'
    VALIDATOR = check.MarkdownValidator

    def test_link_text_extracted(self):
        """Verify that link text and destination are extracted correctly"""
        validator = self._create_validator("""[This is a link](discussion.html)""")
        links = validator.ast.find_links(validator.ast.children[0])

        dest, link_text = validator.ast.get_link_info(links[0])
        self.assertEqual(dest, "discussion.html")
        self.assertEqual(link_text, "This is a link")


class TestIndexPage(BaseTemplateTest):
    """Test the ability to correctly identify and validate specific sections
        of a markdown file"""
    SAMPLE_FILE = "../pages/index.md"
    VALIDATOR = check.IndexPageValidator

    def test_sample_file_passes_validation(self):
        res = self.sample_validator.validate()
        self.assertTrue(res)

    def test_headers_missing_hrs(self):
        validator = self._create_validator("""Blank row

layout: lesson
title: Lesson Title
keywords: ["some", "key terms", "in a list"]

Another section that isn't an HR
""")

        self.assertFalse(validator._validate_doc_headers())

    def test_headers_missing_a_line(self):
        """One of the required headers is missing"""
        validator = self._create_validator("""---
layout: lesson
keywords: ["some", "key terms", "in a list"]
---""")
        self.assertFalse(validator._validate_doc_headers())

    def test_headers_fail_with_other_content(self):
        validator = self._create_validator("""---
layout: lesson
title: Lesson Title
keywords: ["some", "key terms", "in a list"]
otherline: Nothing
---""")
        self.assertFalse(validator._validate_doc_headers())

    def test_headers_fail_because_invalid_content(self):
        validator = self._create_validator("""---
layout: lesson
title: Lesson Title
keywords: this is not a list
---""")
        self.assertFalse(validator._validate_doc_headers())

    def test_index_has_valid_section_headings(self):
        """The provided index page"""
        res = self.sample_validator._validate_section_heading_order()
        self.assertTrue(res)

    def test_file_links_validate(self):
        res = self.sample_validator._validate_links()
        self.assertTrue(res)

    def test_missing_file_fails_validation(self):
        """Fail validation when an html file is linked without corresponding
            markdown file"""
        validator = self._create_validator("""[Broken link](nonexistent.html)""")
        self.assertFalse(validator._validate_links())

    def test_website_link_ignored_by_validator(self):
        """Don't look for markdown if the file linked isn't local-
            remote website links are ignored"""
        validator = self._create_validator("""[Broken link](http://website.com/filename.html)""")
        self.assertTrue(validator._validate_links())

    def test_non_html_link_ignored_by_validator(self):
        """Don't look for markdown if the file linked isn't an html file"""
        # TODO: Revise test for new link criteria
        # TODO: add link test for html pages, including anchors
        validator = self._create_validator("""[Broken link](nonexistent.txt)""")
        self.assertTrue(validator._validate_links())

    def test_index_fail_when_section_heading_absent(self):
        res = self.sample_validator.ast.has_section_heading("Fake heading")
        self.assertFalse(res)

    def test_fail_when_section_headings_in_wrong_order(self):
        validator = self._create_validator("""---
layout: lesson
title: Lesson Title
keywords: ["some", "key terms", "in a list"]
---
Paragraph of introductory material.

> ## Prerequisites
>
> A short paragraph describing what learners need to know
> before tackling this lesson.

## Other Resources

* [Motivation](motivation.html)
* [Reference Guide](reference.html)
* [Instructor's Guide](instructors.html)


## Topics

* [Topic Title 1](01-one.html)
* [Topic Title 2](02-two.html)""")

        self.assertFalse(validator._validate_section_heading_order())

    def test_pass_when_prereq_section_has_correct_heading_level(self):
        validator = self._create_validator("""---
layout: lesson
title: Lesson Title
keywords: ["some", "key terms", "in a list"]
---
Paragraph of introductory material.

> ## Prerequisites
>
> A short paragraph describing what learners need to know
> before tackling this lesson.
""")
        self.assertTrue(validator._validate_intro_section())

    def test_fail_when_prereq_section_has_incorrect_heading_level(self):
        validator = self._create_validator("""---
layout: lesson
title: Lesson Title
keywords: ["some", "key terms", "in a list"]
---
Paragraph of introductory material.

> # Prerequisites
>
> A short paragraph describing what learners need to know
> before tackling this lesson.
""")
        self.assertFalse(validator._validate_intro_section())


class TestTopicPage(BaseTemplateTest):
    """Verifies that the topic page validator works as expected"""
    SAMPLE_FILE = "../pages/01-one.md"
    VALIDATOR = check.TopicPageValidator

    def test_sample_file_passes_validation(self):
        res = self.sample_validator.validate()
        self.assertTrue(res)


class TestMotivationPage(BaseTemplateTest):
    """Verifies that the instructors page validator works as expected"""
    SAMPLE_FILE = "../pages/motivation.md"
    VALIDATOR = check.MotivationPageValidator

    def test_sample_file_passes_validation(self):
        res = self.sample_validator.validate()
        self.assertTrue(res)


class TestReferencePage(BaseTemplateTest):
    """Verifies that the instructors page validator works as expected"""
    SAMPLE_FILE = "../pages/reference.md"
    VALIDATOR = check.ReferencePageValidator

    def test_sample_file_passes_validation(self):
        res = self.sample_validator.validate()
        self.assertTrue(res)


class TestInstructorPage(BaseTemplateTest):
    """Verifies that the instructors page validator works as expected"""
    SAMPLE_FILE = "../pages/instructors.md"
    VALIDATOR = check.InstructorPageValidator

    def test_sample_file_passes_validation(self):
        res = self.sample_validator.validate()
        self.assertTrue(res)


class TestLicensePage(BaseTemplateTest):
    SAMPLE_FILE = '../pages/LICENSE.md'
    VALIDATOR = check.LicensePageValidator

    def test_sample_file_passes_validation(self):
        res = self.sample_validator.validate()
        self.assertTrue(res)

    def test_modified_file_fails_validation(self):
        with open(self.SAMPLE_FILE, 'rU') as f:
            orig_text = f.read()
        mod_text = orig_text.replace("The", "the")
        validator = self._create_validator(mod_text)
        self.assertFalse(validator.validate())


class TestDiscussionPage(BaseTemplateTest):
    SAMPLE_FILE = '../pages/discussion.md'
    VALIDATOR = check.DiscussionPageValidator

    def test_sample_file_passes_validation(self):
        res = self.sample_validator.validate()
        self.assertTrue(res)


if __name__ == "__main__":
    unittest.main()
