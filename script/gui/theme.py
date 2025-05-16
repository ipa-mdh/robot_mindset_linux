from contextlib import contextmanager
from nicegui import ui, app

from .menu import menu

@contextmanager
def frame(navtitle: str, share_dir, footer_generator=None):
    """Custom page frame to share the same styling and behavior across all pages"""
    ui.colors(primary='#000000',
              secondary='#005C7F',
              accent='#111111',
              positive='#10BC69',
              negative='#BC1063',
              warning='#E67614',
              info='#106CBC',
              dark='#1d1d1d',
              dark_page='#000000',
    )
    
    ui.add_css("""
        .my-json-editor {
            /* define a custom theme color */
            --jse-theme-color: #000000;
            --jse-theme-color-highlight: #687177;
        }
    """)
    
    ui.add_head_html('''
        <style>
            /* Default (light mode) */
            .my-header {
                background-color: #ffffff; /* light background */
                color: #000000;
            }

            /* Dark mode override */
            body.body--dark .my-header {
                background-color: #000000; /* dark background */
                color: #000000;
            }
            
            .my-icon {
                filter: invert(0%); /* Normal color for light mode */
            }

            body.body--dark .my-icon {
                filter: invert(90%); /* Invert colors for dark mode */
            }
            
            .my-title {
                color: #000000; /* light text color */
            }
            body.body--dark .my-title {
                color: #dddddd; /* dark text color */
            }
            
            .q-stepper {
                background-color: #fefefe; /* light mode */
                color: #000;
            }
            

            body.body--dark .q-stepper {
                background-color: #000000; /* dark mode */
                color: #fff;
                box-shadow: 0 0 0 0;
            }
            
            body.body--dark .q-stepper__dot {
                background: #fff;
            }

            body.body--dark .q-stepper .q-stepper__tab--active {
                background-color: #333333;
                color: #fff;
            }
            
            body.body--dark .q-stepper .q-stepper__tab--done {
                background-color: #000;
                color: #fff;
            }
            
            .q-btn {
                color: #f00; /* Light mode text */
            }
            
            body.body--dark .q-btn .text-white {
                color: #f00; /* Dark mode text */
            }
        </style>
        ''')

    
    dark = ui.dark_mode()
    
    with ui.header().classes('justify-between my-header'):
        with ui.grid(columns=3).classes('gap-1 w-full wrap'):
            ui.interactive_image(share_dir / 'script/gui/image/robot_mindset.svg', on_mouse=lambda: ui.navigate.to("/"), events=["mouseup"])\
                .classes('my-icon col-span-1 justify-self-start self-start min-w-[150px] max-w-[300px]')
            ui.label(navtitle).classes('my-title col-span-1 justify-self-center text-h4 nowrap whitespace-nowrap')
            with ui.row().classes('col-span-1 justify-self-end'):
                menu(dark)
        ui.separator()
    with ui.grid(columns=1).classes('w-full flex-grow justify-items-center'):
        yield

    if footer_generator:
        with ui.footer().style('background-color: #111B1E;').style('max-height: 250px; padding: 0px;'):
            footer_generator()