from enum import Enum


class RenderStatus(str, Enum):
    """Status of a report rendering job."""
    
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
