from pathlib import Path
from nicegui import ui, app

from . import theme
from .message import message
from .pages import overview, changelog

def footer():
    with ui.expansion('Project: example').classes('w-full').style('margin: 0px; padding: 0px;'):
        with ui.scroll_area().style('max-height: 180px;'):
            ui.code(content="Project details", language='plaintext').classes('w-full')

def create() -> None:
    share_dir = Path('/home/mdh/robot_mindset_linux_ws/robot_mindset_linux')
    
    @ui.page('/')
    def main_page() -> None:
        with theme.frame('Linux Autoinstall', Path('.'), footer_generator=None):
            overview.content(share_dir)

    @ui.page('/changelog')
    def changelog_page():
        with theme.frame('Changelog', share_dir, footer_generator=None):
            changelog.content(share_dir)
