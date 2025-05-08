#!/usr/bin/env python3
from nicegui import ui, events

from uuid import uuid4

class NetworkTable(ui.table):
    def __init__(self, columns, rows, row_key):
        self.columns = columns
        self.rows = rows
        self.row_key = row_key
        
        self._rows = []
        
        # update row with unique id with uuid4
        for row in self.rows:
            buffer = row.copy()
            buffer["id"] = uuid4()
            self._rows.append(buffer)
            
        super().__init__(columns=columns, rows=self._rows, row_key=row_key)

    def add_slot(self, slot_name, slot_content):
        """Add a slot to the table."""
        self.add_slot(slot_name, slot_content)

    def on(self, event_name, callback):
        """Bind an event to a callback."""
        self.on(event_name, callback)

    def update(self):
        """Update the table."""
        self.update()

def main():
    columns = [{'name': 'name', 'label': 'Name', 'field': 'name'},
            {'name': 'ipv4', 'label': 'IPv4 CIDR', 'field': 'ipv4'},
            {'name': 'mac', 'label': 'MAC Address', 'field': 'match.macaddress'}]
    rows = []
    nework_list = [
        {"name": "machine", 'ipv4': '192.168.1.1', "mac": '18:00:ab:00:00:00'},
        {"name": "public", 'ipv4': '10.0.0.1', "mac": '18:00:00:cd:00:01'},
        {"name": "spare", 'ipv4': '192.168.178.1', "mac": '19:00:ef:00:00:11'},
    ]
    
    # update row with unique id with uuid4
    for row in nework_list:
        buffer = row.copy()
        buffer["id"] = uuid4()
        rows.append(buffer)

    def rename(e: events.GenericEventArguments) -> None:
        for row in rows:
            if row["id"] == e.args["id"]:
                row.update(e.args)
        ui.notify(f"Table.rows is now: {table.rows}")


    def delete(e: events.GenericEventArguments) -> None:
        print("----------------")
        print(f"Deleting {e.args['id']}")
        rows[:] = [row for row in rows if str(row["id"]) != e.args["id"]]
        print(f"rows: {rows}")
        ui.notify(f"Delete {e.args['id']}")
        table.update()


    def addrow() -> None:
        newid = uuid4()
        rows.append({"name": "New interfcae", "ipv4": '', "id": newid})
        ui.notify(f"Added new row with id {newid}")
        table.update()


    table = ui.table(columns=columns, rows=rows, row_key="name")
    table.add_slot(
        "header",
        r"""
        <q-tr :props="props">
            <q-th v-for="col in props.cols" :key="col.name" :props="props">
                {{ col.label }}
            </q-th>
            <q-th auto-width />
        </q-tr>
    """,
    )
    table.add_slot(
        "body",
        r"""
        <q-tr :props="props">
            <q-td key="name" :props="props">
                {{ props.row.name }}
                <q-popup-edit v-model="props.row.name" v-slot="scope" 
                    @update:model-value="() => $parent.$emit('rename', props.row)" >
                    <q-input v-model="scope.value" dense autofocus counter @keyup.enter="scope.set" />
                </q-popup-edit>
            </q-td>
            <q-td key="ipv4" :props="props" class="w-8">
                {{ props.row.ipv4 }}
                <q-popup-edit v-model="props.row.ipv4" v-slot="scope" 
                    @update:model-value="() => $parent.$emit('rename', props.row)" >
                    <q-input 
                        v-model="scope.value" 
                        dense autofocus counter 
                        @keyup.enter="scope.set"
                        :rules="[val => /^((25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\.){3}(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\/([0-9]|[12]\d|3[0-2])$/.test(val) || 'Invalid IPv4 address']" />
                </q-popup-edit>
            </q-td>
            <q-td key="mac" :props="props" class="w-8">
                {{ props.row.mac }}
                <q-popup-edit v-model="props.row.mac" v-slot="scope" 
                    @update:model-value="() => $parent.$emit('rename', props.row)" >
                    <q-input 
                        v-model="scope.value"   
                        dense autofocus counter 
                        @keyup.enter="scope.set"
                        :rules="[val => /^([0-9A-Fa-f]{2}([-:])){5}[0-9A-Fa-f]{2}$/.test(val) || 'Invalid MAC address']" />
                </q-popup-edit>
            </q-td>
            <q-td auto-width >
                <q-btn size="sm" color="negative" round dense icon="delete" :props="props"
                    @click="() => $parent.$emit('delete', props.row)" >
            </q-td>
        </q-tr>
        """,
    )
    table.add_slot(
        "bottom-row",
        r"""
        <q-tr :props="props">
            <q-td colspan="4" class="text-center">
                <q-btn color="primary" icon="add" class="w-32" @click="() => $parent.$emit('addrow')"/>
            </q-td>
        </q-tr>
        """,
    )
    table.on("rename", rename)
    table.on("delete", delete)
    table.on("addrow", addrow)