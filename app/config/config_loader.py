from pathlib import Path
from typing import Type, TypeVar, Union

from omegaconf import OmegaConf, DictConfig

T = TypeVar("T")


def load_config(schema_cls: Type[T], config_file: Path) -> T:
    # 1. 创建 schema（用于校验）
    schema = OmegaConf.structured(schema_cls)

    # 2. 加载内容
    content = OmegaConf.load(config_file)

    # 3. 合并 + 校验
    conf = OmegaConf.merge(schema, content)

    # 4. 转为 dataclass 对象
    return OmegaConf.to_object(conf)
