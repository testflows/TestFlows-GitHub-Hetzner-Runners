import sys
import logging

logger = logging.getLogger("testflows.github.runners")


class Action:
    """Action class."""

    debug = False

    def __init__(
        self,
        name: str,
        ignore_fail: bool = False,
        exit_on_fail: bool = True,
        level: int = logging.INFO,
    ):
        self.name = name
        self.ignore_fail = ignore_fail
        self.exit_on_fail = exit_on_fail
        self.level = level

    def __enter__(self):
        logger.log(msg=f"🍀 {self.name}", stacklevel=2, level=self.level)
        return self

    def note(self, message):
        logger.log(msg=f"   {message}", stacklevel=2, level=self.level)

    def __exit__(self, exc_type, exc_value, exc_traceback):
        if exc_value is not None:
            msg = f"❌ Error: {exc_value}"
            if not self.debug:
                logger.log(msg=msg, stacklevel=2, level=self.level)
            else:
                logger.exception(msg=msg, stacklevel=3)
            if self.ignore_fail:
                return True
            if self.debug:
                raise
            if self.exit_on_fail:
                sys.exit(1)
