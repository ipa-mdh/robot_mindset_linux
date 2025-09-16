from loguru import logger
import json

from nicegui import ui, app

from .. import theme
from ..loguru_sink import LoguruSink
from ..message import message

# Build the UI
def content(share_dir) -> None:
    with ui.timeline(side='right').classes('w-2/3 max-w-[400px]'):
        # ui.timeline_entry('Auswahl von Einheiten hinzugefügt.',
        #                 title='Release 0.4.1',
        #                 subtitle='16.9.2024',
        #                 icon='rocket')
        ui.timeline_entry('Max started to implement the Robot Mindest Linux web interface..',
                        title='Initial commit',
                        subtitle='16.5.2025')