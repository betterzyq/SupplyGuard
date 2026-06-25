"""MCP tool errors."""


class ToolError(Exception):
    pass


class ToolPermissionError(ToolError):
    pass


class ToolNotFoundError(ToolError):
    pass
