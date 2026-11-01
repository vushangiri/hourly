import os
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from hourly.models import Base


@pytest.fixture
def database():
    url=os.environ.get('TEST_DATABASE_URL')
    if not url:
        pytest.skip('TEST_DATABASE_URL not set: requires a disposable PostgreSQL database')
    if 'test' not in url.rsplit('/',1)[-1]:
        pytest.fail('Refusing to reset a database whose name does not contain test')
    engine=create_engine(url,pool_size=10,max_overflow=10)
    with engine.begin() as c:
        Base.metadata.drop_all(c)
        Base.metadata.create_all(c)
    factory=sessionmaker(engine,expire_on_commit=False)
    yield factory
    engine.dispose()
