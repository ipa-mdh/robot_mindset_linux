from nicegui import ui, app

from . import theme
from .message import message
from .pages import overview, changelog

from .utils.user_storage import UserStorage
    

def footer():
    with ui.expansion('Project: example').classes('w-full').style('margin: 0px; padding: 0px;'):
        with ui.scroll_area().style('max-height: 180px;'):
            ui.code(content="Project details", language='plaintext').classes('w-full')

def create() -> None:
    
    data = None
    
    @ui.page('/')
    def main_page() -> None:
        data = UserStorage()
        with theme.frame('Linux', footer_generator=None):
            overview.content(data)

    @ui.page('/changelog')
    def changelog_page():
        with theme.frame('Changelog', footer_generator=None):
            changelog.content(data)
