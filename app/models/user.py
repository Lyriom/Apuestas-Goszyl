from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class User(Base):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(primary_key=True)
    keycloak_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), default='')
    roles: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def has_role(self, *requested: str) -> bool:
        saved_roles = {saved_role.lower() for saved_role in (self.roles or [])}
        requested_roles = {role.lower() for role in requested}
        admin_aliases = {'admin', 'realm-admin', 'manage-realm', 'manage-users', 'sistema-b-admin'}
        if 'admin' in requested_roles and saved_roles.intersection(admin_aliases):
            return True
        return bool(saved_roles.intersection(requested_roles))
