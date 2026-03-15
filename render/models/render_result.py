from pydantic import BaseModel
from typing import Optional
from .render_status import RenderStatus


class RenderResult(BaseModel):
    """Result of a report rendering operation.
    
    Attributes:
        status: Current status of the rendering job
        pdf_bytes: PDF file content as bytes (only present when status is COMPLETED)
        error_message: Error description (only present when status is FAILED)
    """
    
    status: RenderStatus
    pdf_bytes: Optional[bytes] = None
    error_message: Optional[str] = None
    
    class Config:
        """Pydantic configuration."""
        arbitrary_types_allowed = True
