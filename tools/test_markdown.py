import unittest
import validate_markdown_template

validate_markdown_template.start_logging()  # Make log messages visible to help audit test failures


class TestHomePage(unittest.TestCase):
    """Test the ability to correctly identify and validate specific sections of a markdown file"""
    def setUp(self):
        self.sample_file = validate_markdown_template.HomePageValidator('../pages/index.md')  # Passes tests

    def _create_validator(self, markdown):
        """Create validator object from markdown string; useful for failures"""
        return validate_markdown_template.HomePageValidator(markdown=markdown)

    def test_headers_missing_hrs(self):
        validator = self._create_validator("""Blank row

layout: lesson
title: Lesson Title
keywords: ["some", "key terms", "in a list"]

Another section that isn't an HR
""")

        self.assertEqual(validator._validate_doc_headers(), False)

    def test_headers_missing_a_line(self):
        """One of the required headers is missing"""
        validator = self._create_validator("""---
layout: lesson
keywords: ["some", "key terms", "in a list"]
---""")
        self.assertEqual(validator._validate_doc_headers(), False)

    def test_headers_fail_with_other_content(self):
        validator = self._create_validator("""---
layout: lesson
title: Lesson Title
keywords: ["some", "key terms", "in a list"]
otherline: Nothing
---""")
        self.assertEqual(validator._validate_doc_headers(), False)

    def test_headers_fail_because_invalid_content(self):
        validator = self._create_validator("""---
layout: lesson
title: Lesson Title
keywords: this is not a list
---""")
        self.assertEqual(validator._validate_doc_headers(), False)

    def test_index_has_valid_section_headings(self):
        """The provided index page"""
        res = self.sample_file._validate_section_heading_order()
        self.assertEqual(res, True)

    def test_file_links_validate(self):
        res = self.sample_file._validate_links()
        self.assertEqual(res, True)

    def test_missing_file_fails_validation(self):
        """Fail validation when an html file is linked without corresponding markdown file"""
        validator = self._create_validator("""[Broken link](nonexistent.html)""")
        self.assertEqual(validator._validate_links(), False)

    def test_website_link_ignored_by_validator(self):
        """Don't look for markdown if the file linked isn't local- remote website links are ignored"""
        validator = self._create_validator("""[Broken link](http://website.com/filename.html)""")
        self.assertEqual(validator._validate_links(), True)

    def test_non_html_link_ignored_by_validator(self):
        """Don't look for markdown if the file linked isn't an html file"""
        validator = self._create_validator("""[Broken link](nonexistent.txt)""")
        self.assertEqual(validator._validate_links(), True)

    def test_index_fail_when_section_heading_absent(self):
        res = self.sample_file.ast.has_section_heading("Fake heading")
        self.assertEqual(res, False)

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

        self.assertEqual(validator._validate_section_heading_order(), False)

if __name__ == "__main__":
    unittest.main()