import os
import sys

sys.path.insert(0, os.path.abspath("../src"))  # Correct path to your source

print()

# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = "beancount-gocardless"
copyright = "2025, forgx1"
author = "forgx1"
release = "0.1.0"

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx.ext.autodoc.typehints",
]
# Add this to enable Markdown in docstrings:
autodoc_mock_imports = ["requests", "requests-cache", "beancount", "beangulp", "pyyaml"]
autodoc_default_options = {
    "members": True,
    "undoc-members": True,
    "show-inheritance": True,
    "special-members": "__init__",
}
autodoc_typehints = "description"

# Napoleon settings for Google and NumPy style docstrings
napoleon_google_docstring = True
napoleon_numpy_docstring = True
napoleon_use_param = True
napoleon_use_rtype = True
napoleon_use_ivar = True
templates_path = ["_templates"]

exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# Enable proper parsing of markdown in docstrings
source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}

# MyST parser settings for markdown support
myst_parse_docstrings = True
myst_enable_extensions = [
    "colon_fence",
    "deflist",
]


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]
