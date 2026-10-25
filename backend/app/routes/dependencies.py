from typing import Annotated

from fastapi import Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db

DatabaseSession = Annotated[Session, Depends(get_db)]
PageLimit = Annotated[int, Query(ge=1, le=100)]
PageOffset = Annotated[int, Query(ge=0)]
