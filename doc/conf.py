# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

import subprocess
import datetime

project = 'CraneIQ Pro User Manual for EDGE UI'
buildtime = datetime.datetime.now()
buildtag = f'{buildtime.strftime("%B %Y")}'
buildyear = buildtime.strftime("%Y")
copyright = f'{buildyear}, Innospace Automation Services Pvt Ltd'
author = 'Innospace Automation Services Pvt Ltd'
#try:
    #version = subprocess.check_output(['git-semver', '../']).strip().decode('ascii')
#except Exception as e:
version = 'r002'
release = version

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    'sphinx.ext.imgconverter',
    'sphinx_simplepdf'
]

templates_path = ['_templates']
exclude_patterns = []

#if not 'dev' in version:
    #exclude_patterns.append('common/disclaimer/disclaimer_version_unstable.rst')
#if not version == 'unknown':
    #exclude_patterns.append('common/disclaimer/disclaimer_version_unknown.rst')

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'classic'
html_static_path = ['_static']
html_show_sourcelink = False
html_show_sphinx = False

# -- Options for PDF output --------------------------------------------------
latex_elements = {
    'extraclassoptions': 'openany,oneside'
}

# SimplePDF configuration
simplepdf_vars = {
    'primary': '#F99325',
    'primary-opaque': '#F99325',
    'secondary': '#5D0D00',
    'links': '#FFA034',
    'cover-bg': 'rgb(249, 147, 37)',
    'top-center-content': '"Innospace Automation Services Pvt Ltd"',
    'bottom-left-content': f'"{project} (Release {release})"',
    'bottom-right-content': f'"{buildtag}"'
}
