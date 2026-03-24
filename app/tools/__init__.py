"""Tool package import side-effects for global registry population.

Importing this package guarantees all built-in tools are registered.
"""

import app.tools.filesystem  # noqa: F401
import app.tools.execution  # noqa: F401
import app.tools.git_tools  # noqa: F401
import app.tools.news_tools  # noqa: F401
import app.tools.spreadsheet_tools  # noqa: F401
import app.tools.web_fetch_tools  # noqa: F401

