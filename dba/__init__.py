"""DBA session telemetry: text-to-SQL over the monitoring workbook.

This package is deliberately separate from ``factory_knowledge`` because it
solves a different problem. The factory corpus is prose, so RAG works. This
workbook is 2,372 rows of numeric telemetry, where the answer to "which database
burns the most CPU?" is a SUM over every row — something retrieval cannot do.

Standalone use::

    from dba import DBAAgent
    print(DBAAgent().ask("Which database used the most CPU?").text)

Or from the command line::

    python -m dba "which sessions are blocking others?"
"""

from .agent import DBAAgent, DBAAnswer
from .store import DBAError, SessionStore, get_store

__all__ = ["DBAAgent", "DBAAnswer", "DBAError", "SessionStore", "get_store"]
