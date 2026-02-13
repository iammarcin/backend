import pytest
import bcrypt
from sqlalchemy import select


pytestmark = pytest.mark.requires_docker

from core.exceptions import DatabaseError
from features.db.ufc.db_models import Person
from features.db.ufc.repositories.auth import AuthRepository


@pytest.mark.asyncio
async def test_register_user_hashes_password(session):
    repo = AuthRepository()
    plain_password = "super-secret"

    person = await repo.register_user(
        session,
        account_name="Hasher",
        email="hash@example.com",
        password=plain_password,
    )

    assert person.id is not None
    assert person.password != plain_password
    assert bcrypt.checkpw(plain_password.encode("utf-8"), person.password.encode("utf-8"))

    result = await session.execute(select(Person).where(Person.email == "hash@example.com"))
    stored = result.scalars().first()
    assert stored is not None
    assert stored.password == person.password


@pytest.mark.asyncio
async def test_authenticate_user_validates_password(session):
    repo = AuthRepository()
    await repo.register_user(
        session,
        account_name="Login",
        email="login@example.com",
        password="password123",
    )

    valid = await repo.authenticate_user(
        session, email="login@example.com", password="password123"
    )
    assert valid is not None

    invalid = await repo.authenticate_user(
        session, email="login@example.com", password="wrong"
    )
    assert invalid is None


@pytest.mark.asyncio
async def test_user_exists_and_profile(session):
    repo = AuthRepository()
    await repo.register_user(
        session,
        account_name="Existing",
        email="exists@example.com",
        password="password123",
    )

    exists = await repo.user_exists(session, email="exists@example.com")
    assert exists is True

    profile = await repo.get_user_profile(session, email="exists@example.com")
    assert profile is not None
    assert profile.account_name == "Existing"

    missing = await repo.user_exists(session, email="missing@example.com")
    assert missing is False


@pytest.mark.asyncio
async def test_register_duplicate_raises_database_error(session):
    repo = AuthRepository()
    await repo.register_user(
        session,
        account_name="Duplicate",
        email="dup@example.com",
        password="password123",
    )

    with pytest.raises(DatabaseError) as exc_info:
        await repo.register_user(
            session,
            account_name="Duplicate",
            email="dup@example.com",
            password="password123",
        )

    assert exc_info.value.operation == "register_user_duplicate"
