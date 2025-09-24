"""
singleton.py

Singleton metaclass for creating singleton classes

Author: Nathan Swanson
"""

from typing import ClassVar


class SingletonMeta(type):
    _instances: ClassVar = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]
