"""
GoCardless Bank Account Data API client and Beancount importer.

Provides a typed API client with Pydantic models and a beangulp importer
for converting GoCardless transactions into Beancount directives.
"""

from importlib.metadata import version

from .client import GoCardlessClient
from .importer import GoCardlessImporter

__all__ = ["GoCardlessClient", "GoCardlessImporter"]
__version__ = version("beancount-gocardless")
