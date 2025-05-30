from uuid import uuid4
from nicegui import ui, events
from loguru import logger

DEFAULT_COLUMNS = [{'name': 'name', 'label': 'Name', 'field': 'name', 'classed': 'overflow-auto'},]

class SimpleTable:
    """
    Encapsulates a dynamic network interface table with add, rename, and delete capabilities.
    """
    def __init__(self, rows, columns=None, update_callback=None):
        # Define table columns
        if columns is None:
            self.columns = DEFAULT_COLUMNS
        else:
            self.columns = columns
        
        self.rows = []
        self._init_rows(rows)
        self._update_callback = update_callback

        # Create the UI table
        self.table = ui.table(columns=self.columns, rows=self.rows, row_key="name") \
            .classes('w-full')

        # Setup custom slots
        self._setup_slots()

        # Register event handlers
        self._register_handlers()

    def _init_rows(self, rows):
        for item in rows:
            row = item.copy()
            row['id'] = uuid4()
            self.rows.append(row)

    def _setup_slots(self):
        # Header slot
        self.table.add_slot(
            'header',
            r"""
            <q-tr :props="props">
                <q-th v-for="col in props.cols" :key="col.name" :props="props">
                    {{ col.label }}
                </q-th>
                <q-th auto-width />
            </q-tr>
            """
        )
        # Body slot with editable fields and delete button
        self.table.add_slot(
            'body',
            r"""
            <q-tr :props="props">
                <q-td key="name" :props="props">
                    {{ props.row.name }}
                    <q-popup-edit v-model="props.row.name" v-slot="scope"
                        @update:model-value="() => $parent.$emit('rename', props.row)">
                        <q-input v-model="scope.value" dense autofocus counter @keyup.enter="scope.set" />
                    </q-popup-edit>
                </q-td>
                <q-td auto-width>
                    <q-btn size="sm" color="negative" round dense icon="delete"
                        @click="() => $parent.$emit('delete', props.row)" />
                </q-td>
            </q-tr>
            """
        )
        # Bottom row slot with add button
        self.table.add_slot(
            'bottom-row',
            r"""
            <q-tr :props="props">
                <q-td colspan="2" class="text-center">
                    <q-btn color="primary" icon="add" class="w-32"
                        @click="() => $parent.$emit('addrow')" />
                </q-td>
            </q-tr>
            """
        )

    def _register_handlers(self):
        self.table.on('rename', self.rename)
        self.table.on('delete', self.delete)
        self.table.on('addrow', self.addrow)

    def rename(self, e: events.GenericEventArguments) -> None:
        """
        Rename a row matching the event ID.
        """
        for row in self.rows:
            if str(row['id']) == e.args['id']:
                row.update(e.args)
        if self._update_callback:
            self._update_callback(self.rows)
        logger.debug(f"Table.rows is now: {self.rows}")

    def delete(self, e: events.GenericEventArguments) -> None:
        """
        Delete the row matching the event ID.
        """
        logger.debug(f"Deleting {e.args['id']}")
        self.rows[:] = [row for row in self.rows if str(row['id']) != e.args['id']]
        logger.debug(f"Rows after delete: {self.rows}")
        if self._update_callback:
            self._update_callback(self.rows)
        self.table.update()

    def addrow(self) -> None:
        """
        Add a blank new row.
        """
        new_id = uuid4()
        self.rows.append({'name': 'New Entry','id': new_id})
        logger.debug(f"Added new row with id {new_id}")
        if self._update_callback:
            self._update_callback(self.rows)
        self.table.update()

# Example usage:
# if __name__ == '__main__':
#     network_list = [
#         {'name': 'machine'},
#         {'name': 'public'},
#         {'name': 'spare'},
#     ]
#     manager = SimpleTable(network_list)
