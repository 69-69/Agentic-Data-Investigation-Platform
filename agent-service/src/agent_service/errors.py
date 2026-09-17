class ToolError(Exception):
    """Code-only exception; driver/model error bodies never reach graph state."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)
