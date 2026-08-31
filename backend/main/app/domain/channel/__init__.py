"""Conversational channels that front the canonical backend (PRD §7.3).

A channel is a thin surface: it renders and writes the same state the website does,
through the same services. Nothing about a case lives here.
"""
from main.app.domain.channel import whatsapp  # noqa: F401
