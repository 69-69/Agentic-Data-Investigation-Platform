import pytest

from agent_service.config import Settings
from agent_service.tools.database import FixtureDatabase
from agent_service.tools.guard import SqlGuard


@pytest.fixture
def settings():
    return Settings(_env_file=None, agent_mode="development", sql_backend="fixture")


@pytest.fixture
def guard(settings):
    return SqlGuard(settings.allowed_tables, settings.sql_default_row_limit, settings.sql_max_row_limit)


@pytest.fixture
async def database(settings, guard):
    db = FixtureDatabase(settings, guard)
    yield db
    await db.close()
