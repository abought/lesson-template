import unittest
import validate_markdown_template

validate_markdown_template.start_logging()  # Make log messages visible to help audit test failures


class TestHomePage(unittest.TestCase):
    """Test the ability to correctly identify and validate specific sections of a markdown file"""
    def setUp(self):
        self.sample_file = validate_markdown_template.HomePageValidator('../index.md')  # Passes tests

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

    def test_index_has_valid_headings(self):
        """The provided index page"""
        res = self.sample_file._validate_section_headings()
        self.assertEqual(res, True)

    def test_index_invalid_headings_cause_error(self):
        res = self.sample_file.ast.has_section_heading("Fake heading")
        self.assertEqual(res, False)


if __name__ == "__main__":
    unittest.main()