from nicegui import ui, app


def menu(dark) -> None:
    # def logout() -> None:
    #     app.storage.user.clear()
    #     ui.navigate.to('/login')
    # ui.link('Home', '/').classes(replace='text-white')
    # ui.link('A', '/a').classes(replace='text-white')
    # ui.link('B', '/b').classes(replace='text-white')
    # ui.link('TROS', '/TROS').classes(replace='text-white')

    with ui.row().classes('w-full items-center justify-self-end'):
        with ui.button(icon='menu'):
            with ui.menu().classes('w-32') as menu:
                ui.menu_item('Home', on_click=lambda: ui.navigate.to('/'))
                ui.menu_item('Changelog', on_click=lambda: ui.navigate.to('/changelog'))
                ui.switch('Dark mode').bind_value(dark)
                # ui.menu_item('Logout', on_click=logout)
                # ui.menu_item('Menu item 3 (keep open)',
                #             lambda: result.set_text('Selected item 3'), auto_close=False)
                # ui.separator()
                # ui.menu_item('close', on_click=menu.close)

