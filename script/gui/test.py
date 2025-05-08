from nicegui import ui
import json

ui.label('Table with IPv4/CIDR Mask')

# 1) Load IMask.js so Quasar’s mask-options can see it:
ui.add_head_html('<script src="https://unpkg.com/imask"></script>')

# 2) Pre-define the mask options as a Python dict:
ip_mask_options = {
    'mask':          'i.i.i.i/n',
    'blocks': {
        # each 'i' block → 0–255
        'i': {
            'mask':       'IMask.MaskedRange',
            'from':       0,
            'to':         255,
            'maxLength':  3
        },
        # the 'n' block → CIDR suffix 0–32
        'n': {
            'mask':       'IMask.MaskedRange',
            'from':       0,
            'to':         32,
            'maxLength':  2
        }
    },
    'lazy': False      # always show the dots and slash
}

# 3) Create your table and body slot exactly as before, but now
#    interpolate the JSON-serialized mask-options into :mask-options

network_columns = [{'name': 'name', 'label': 'Name', 'field': 'name'},
                   {'name': 'ipv4', 'label': 'IPv4 CIDR', 'field': 'ipv4'},
                   {'name': 'mac', 'label': 'MAC Address', 'field': 'mac'}]
network_list = [
        {'name': 'machine', 'ipv4': '192.168.1.1', 'mac': '18:00:ab:00:00:00'},
        {'name': 'public',  'ipv4': '10.0.0.1',    'mac': '18:00:00:cd:00:01'},
        {'name': 'spare',   'ipv4': '192.168.178.1','mac': '19:00:ef:00:00:11'},
]
table = ui.table(
    columns=network_columns,
    rows=network_list,
)

# Header slot
table.add_slot(
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

table.add_slot(
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
                    dense autofocus
                    @keyup.enter="scope.set"
                    mask
                    :mask-options='{json.dumps(ip_mask_options)}'
                    :rules="[
                        val =>
                            /^((25[0-5]|2[0-4]\\d|1\\d\\d|[1-9]?\\d)\\.){3}(25[0-5]|2[0-4]\\d|1\\d\\d|[1-9]?\\d)\\/(?:[0-9]|[12]\\d|3[0-2])$/.test(val)
                            || 'Invalid IPv4/CIDR'
                        ]"
                />    
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

ui.run(title='Table with IPv4/CIDR Mask')
