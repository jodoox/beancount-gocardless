"""
Simple GoCardless Bank Account Data API Client
Generated from swagger.json to provide a clean, typed interface.
"""

from .client import GoCardlessClient
from .importer import GoCardLessImporter
from .models import *

__all__ = ["GoCardlessClient", "GoCardLessImporter"]
