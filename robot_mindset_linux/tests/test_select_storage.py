import importlib.util
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "script/seed/template/dev/seed/data/autoinstall/bin/select_storage.py"
SPEC = importlib.util.spec_from_file_location("select_storage", MODULE_PATH)
select_storage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(select_storage)


class SelectStorageTests(unittest.TestCase):
    def test_parse_parted_output_detects_free_rows_on_populated_disk(self):
        output = """BYT;
/dev/sda:68719476736B:scsi:512:512:gpt:QEMU QEMU HARDDISK:;
1:17408B:1048575B:1031168B:free;
1:1048576B:5242879B:4194304B:::bios_grub;
2:5242880B:1078984703B:1073741824B:fat32::boot, esp;
3:1078984704B:10742661119B:9663676416B:ext4::;
4:10742661120B:68718428159B:57975767040B:::;
1:68718428160B:68719459839B:1031680B:free;
"""
        table_type, free_regions = select_storage.parse_parted_output(output, "/dev/sda")
        self.assertEqual(table_type, "gpt")
        self.assertEqual(
            free_regions,
            [
                {"start": 17408, "end": 1048575, "size": 1031168},
                {"start": 68718428160, "end": 68719459839, "size": 1031680},
            ],
        )

    def test_select_disk_allows_empty_disks_below_free_space_threshold(self):
        disks = [
            {
                "path": "/dev/sdb",
                "size": 20 * 1024 ** 3,
                "is_ssd": False,
                "partitions": [],
                "largest_free": {"start": 0, "end": 20 * 1024 ** 3, "size": 20 * 1024 ** 3},
            }
        ]
        selection = select_storage.select_disk(disks, min_free_bytes=40 * 1024 ** 3, prefer_ssd=True)
        self.assertIsNotNone(selection)
        self.assertEqual(selection["scenario"], "whole-disk")
        self.assertEqual(selection["path"], "/dev/sdb")

    def test_select_disk_prefers_populated_disk_with_large_free_region(self):
        disks = [
            {
                "path": "/dev/sda",
                "size": 100 * 1024 ** 3,
                "is_ssd": False,
                "partitions": [{"number": 1}],
                "largest_free": {"start": 1, "end": 50, "size": 60 * 1024 ** 3},
            },
            {
                "path": "/dev/sdb",
                "size": 200 * 1024 ** 3,
                "is_ssd": True,
                "partitions": [],
                "largest_free": {"start": 0, "end": 10, "size": 200 * 1024 ** 3},
            },
        ]
        selection = select_storage.select_disk(disks, min_free_bytes=40 * 1024 ** 3, prefer_ssd=True)
        self.assertEqual(selection["path"], "/dev/sda")
        self.assertEqual(selection["scenario"], "free-space")

    def test_update_autoinstall_rewrites_storage_yaml_without_key_order_assumptions(self):
        content = """apt:\n  fallback: offline-install\nearly-commands:\n- echo test\nidentity:\n  hostname: demo\nstorage:\n  version: 1\n  config: []\nupdates: security\n"""
        storage_config = {"version": 1, "config": [{"type": "disk", "id": "disk-test"}]}
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "autoinstall.yaml"
            path.write_text(content, encoding="utf-8")
            select_storage.update_autoinstall(str(path), storage_config)
            updated = path.read_text(encoding="utf-8")
        self.assertIn("disk-test", updated)
        self.assertIn("early-commands", updated)
        self.assertIn("updates", updated)


if __name__ == "__main__":
    unittest.main()
