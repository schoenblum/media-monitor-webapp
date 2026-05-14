"""ORM models — imported here so Alembic autogenerate can discover them."""
from app.models.language import UniversityLanguage  # noqa: F401
from app.models.outlet import Outlet, SearchOutletLink  # noqa: F401
from app.models.result import Result  # noqa: F401
from app.models.run import Run, RunStatus, RunTrigger  # noqa: F401
from app.models.search import Search, SearchTerm  # noqa: F401
from app.models.user import PasswordResetToken, User, UserRole  # noqa: F401
