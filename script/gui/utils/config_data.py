# In robot_mindset/utils/config_data.py
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, Optional

@dataclass
class ConfigData:
    share_dir: Path
    spark_list: Dict[str, dict] = field(default_factory=dict)
    spark_list_callback: Optional[Callable[[], None]] = None
    get_spark_parameters_fnc: Optional[Callable[[str], str]] = None
    set_spark_parameters_fnc: Optional[Callable[[str, dict], None]] = None
    use_heardbeat: bool = False
