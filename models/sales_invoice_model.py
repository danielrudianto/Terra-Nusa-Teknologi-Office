from pydantic import BaseModel
from datetime import datetime as dt, date as d

class SalesInvoice(BaseModel):
    name: str  # Name of the sales invoice
    date: d  # Date of the sales invoice in ISO format
    projectName: str  # Name of the project
    clientID: int  # ID of the client