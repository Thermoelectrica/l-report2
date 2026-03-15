from pydantic import BaseModel, Field
from typing import List, Any, Optional
from enum import Enum


class ParameterType(str, Enum):
    """Supported parameter data types for report parameters.
    
    Attributes:
        STRING: Text value
        INTEGER: Whole number
        FLOAT: Decimal number
        BOOLEAN: True/False value
        DATE: Date in ISO format (YYYY-MM-DD)
        DATETIME: Date and time in ISO format (YYYY-MM-DDTHH:MM:SS)
    """

    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    DATE = "date"
    DATETIME = "datetime"


class ReportParameter(BaseModel):
    """Definition of a report parameter.
    
    Describes a single parameter that a report accepts, including its type,
    validation rules, and default value. Use this to build dynamic forms
    and validate user input.
    
    Attributes:
        name: Parameter identifier used in the params dictionary
        type: Data type of the parameter
        required: Whether this parameter must be provided
        description: Optional human-readable description for UI display
        enum: Optional list of allowed values (for dropdown/select inputs)
        default: Optional default value if parameter is not provided
        
    Example:
        >>> param = ReportParameter(
        ...     name="start_date",
        ...     type=ParameterType.DATE,
        ...     required=True,
        ...     description="Report start date"
        ... )
    """
    
    name: str = Field(description="Parameter identifier")
    type: ParameterType = Field(description="Parameter data type")
    required: bool = Field(
        default=False,
        description="Whether this parameter is required"
    )
    description: Optional[str] = Field(
        default=None,
        description="Human-readable parameter description"
    )
    enum: Optional[List[Any]] = Field(
        default=None,
        description="List of allowed values (for constrained inputs)"
    )
    default: Optional[Any] = Field(
        default=None,
        description="Default value if not provided"
    )


class ReportMetadata(BaseModel):
    """Comprehensive metadata for a report.
    
    Contains all information needed to understand and render a report,
    including its parameters, version, and execution constraints.
    
    Attributes:
        id: Unique report identifier
        name: User-friendly display name
        description: Optional detailed description of what the report does
        version: Report version string (default: "1.0")
        timeout: Optional maximum execution time in seconds. If rendering
                exceeds this time, it should be terminated.
        parameters: List of parameter definitions that the report accepts.
                   Use these to build input forms and validate user input.
    """

    id: str
    name: str
    description: Optional[str] = None
    version: str = "1.0"
    timeout: Optional[int] = Field(
        default=None,
        description="Maximum rendering time in seconds"
    )
    parameters: List[ReportParameter] = Field(
        default_factory=list,
        description="List of parameters this report accepts"
    )

