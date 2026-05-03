"""Deprecated: use beancount_openbanking.providers.gocardless instead."""

from beancount_openbanking.providers.gocardless import (
    GoCardlessProvider as GoCardlessClient,
)

GoCardLessClient = GoCardlessClient

__all__ = ["GoCardlessClient", "GoCardLessClient"]
