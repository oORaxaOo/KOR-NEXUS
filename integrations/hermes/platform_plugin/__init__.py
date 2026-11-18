"""Hermes user-plugin entry point for the KOR-NEXUS Gateway platform."""

from .adapter import register

__all__ = ["register"]
