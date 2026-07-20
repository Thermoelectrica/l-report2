"""Models for the report2 web application."""

from typing import List
from pydantic import BaseModel


class ParamInfo(BaseModel):
    """Parameter information for UI rendering."""

    name: str
    type: str
    required: bool
    description: str
    placeholder: str = ""
    enum_values: List[str] = []
    value: str = ""  # Current value (initialized with default, then tracks user input)
