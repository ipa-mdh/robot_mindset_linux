from uuid import uuid4
from nicegui import ui, events
from loguru import logger

network_columns = [{'name': 'name', 'label': 'Name', 'field': 'name'},
                   {'name': 'ipv4', 'label': 'IPv4 CIDR', 'field': 'ipv4'},
                   {'name': 'mac', 'label': 'MAC Address', 'field': 'mac'}]

def get_network_table_rows(network_list):
    """Create rows for the network table."""
    logger.debug(network_list)
    rows = []
    for item in network_list:
        row = item.copy()
        row['mac'] = row.get('match', {}).get('macaddress', '')
        rows.append(row)
    return rows

def get_networks(network_table_rows):
    """Get the networks from the table rows."""
    logger.debug(network_table_rows)
    networks = []
    for row in network_table_rows:
        network = {
            'name': row.get('name', ''),
            'ipv4': row.get('ipv4', ''),
            'match': {'macaddress': row.get('mac', '')}
        }
        networks.append(network)
    return networks

class NetworkTable:
    """
    Encapsulates a dynamic network interface table with add, rename, and delete capabilities.
    """
    def __init__(self, network_list, columns=None):
        # Define table columns
        if columns is None:
            self.columns = network_columns
        else:
            self.columns = columns
        # Initialize rows with UUIDs
        self.rows = []
        self._init_rows(network_list)

        # Create the UI table
        self.table = ui.table(columns=self.columns, rows=self.rows, row_key="name")

        # Setup custom slots
        self._setup_slots()

        # Register event handlers
        self._register_handlers()

    def _init_rows(self, network_list):
        for item in network_list:
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
                <q-td key="ipv4" :props="props" class="w-8">
                    {{ props.row.ipv4 }}
                    <q-popup-edit v-model="props.row.ipv4" v-slot="scope"
                        @update:model-value="() => $parent.$emit('rename', props.row)">
                        <q-input
                            v-model="scope.value"
                            dense autofocus counter
                            @keyup.enter="scope.set"
                            :rules="[
                                // 1) IP-octets only
                                val => {
                                    const ip = val.split('/')[0];
                                    const ok = /^((25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\.){3}(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)$/.test(ip);
                                    return ok || 'Invalid IPv4 address';
                                },
                                // 2) CIDR suffix only
                                val => {
                                    const parts = val.split('/');
                                    if (parts.length < 2 || parts[1] === '') {
                                    return 'Missing CIDR suffix';
                                    }
                                    const ok = /^([0-9]|[12]\d|3[0-2])$/.test(parts[1]);
                                    return ok || 'CIDR suffix must be 0–32';
                                }
                                ]"
                            mask
                            :mask-options="" />
                            
                    </q-popup-edit>
                </q-td>
                <q-td key="mac" :props="props" class="w-8">
                    {{ props.row.mac }}
                    <q-popup-edit v-model="props.row.mac" v-slot="scope"
                        @update:model-value="() => $parent.$emit('rename', props.row)">
                        <q-input
                            v-model="scope.value"
                            dense autofocus counter
                            @keyup.enter="scope.set"
                            placeholder="__:__:__:__:__:__"
                            :rules="[val => /^([0-9A-Fa-f]{2}([-:])){5}[0-9A-Fa-f]{2}$/.test(val) || 'Invalid MAC address']" />
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
                <q-td colspan="4" class="text-center">
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
        logger.debug(f"Table.rows is now: {self.rows}")

    def delete(self, e: events.GenericEventArguments) -> None:
        """
        Delete the row matching the event ID.
        """
        logger.debug(f"Deleting {e.args['id']}")
        self.rows[:] = [row for row in self.rows if str(row['id']) != e.args['id']]
        logger.debug(f"Rows after delete: {self.rows}")
        self.table.update()

    def addrow(self) -> None:
        """
        Add a blank new interface row.
        """
        new_id = uuid4()
        self.rows.append({'name': 'New interface', 'ipv4': '', 'mac': '', 'id': new_id})
        logger.debug(f"Added new row with id {new_id}")
        self.table.update()

# Example usage:
# if __name__ == '__main__':
#     network_list = [
#         {'name': 'machine', 'ipv4': '192.168.1.1', 'mac': '18:00:ab:00:00:00'},
#         {'name': 'public',  'ipv4': '10.0.0.1',    'mac': '18:00:00:cd:00:01'},
#         {'name': 'spare',   'ipv4': '192.168.178.1','mac': '19:00:ef:00:00:11'},
#     ]
#     manager = NetworkTable(network_list)
