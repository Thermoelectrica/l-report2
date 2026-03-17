from typing import Optional

from pydantic import BaseModel

from .render_status import RenderStatus


class RenderResult(BaseModel):
    """Result of a report rendering operation.

    Attributes:
        status: Current status of the rendering job
        file_path: Relative path to the PDF file (for URL generation)
        filename: Filename for the PDF
        error_message: Error description (only present when status is FAILED)
    """

    status: RenderStatus
    file_path: Optional[str] = None
    filename: Optional[str] = None
    error_message: Optional[str] = None
