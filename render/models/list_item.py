from pydantic import BaseModel


class ReportListItem(BaseModel):
    """Minimal information about a report for listing purposes.
    
    Attributes:
        id: Unique report identifier used for API calls
        name: User-friendly display name for the report
    """
    
    id: str
    name: str