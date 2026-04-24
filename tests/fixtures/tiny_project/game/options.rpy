## options.rpy — minimal config for the renpy-mcp fixture project.

define config.name = _("Tiny Fixture")
define config.version = "0.1.0"
define gui.show_name = True

define build.name = "tiny_fixture"

init python:
    build.classify("**~", None)
    build.classify("**.bak", None)
