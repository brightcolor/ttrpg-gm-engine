import os
import tempfile

os.environ["DATABASE_URL"] = "sqlite:///" + tempfile.mktemp(suffix=".db")
os.environ["DEMO_MODE"] = "true"

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.base import Base
from app.models import *  # noqa: F401,F403
from app.services.rulesets import ensure_builtin_rulesets


@pytest.fixture()
def db():
    engine = create_engine(os.environ["DATABASE_URL"])
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    ensure_builtin_rulesets(session)
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)

