from .xcancel import XCancelListener


def register(app):
    app.event("message")(XCancelListener().handle)
