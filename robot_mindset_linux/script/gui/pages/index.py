from nicegui import ui

dark = ui.dark_mode()
ui.switch('Dark mode').bind_value(dark)


with ui.row().style('flex-direction: column; align-items: center;'):
    ui.label('Welcome to My Page')
    ui.button('Scroll to Dialog', on_click=lambda: ui.navigate.to('#dialog'))

ui.separator()

ui.element('div').style('height: 100vh; background-color: lightblue;')

# Add some space to scroll down
ui.label(' ' * 1000)

with ui.dialog() as dialog:
    ui.label('This is the Dialog')
    ui.button('Close', on_click=dialog.close)
    dialog.props('persistent')


ui.link_target('dialog')  # Link the dialog to the anchor
ui.label('This is the anchor for the dialog')
# Add anchor
# ui.html('<div id="dialog"></div>')

# Enable smooth scroll via CSS
ui.add_head_html('''
<style>
html {
  scroll-behavior: smooth;
}
</style>
''')

ui.run()
