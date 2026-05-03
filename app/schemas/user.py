from pydantic import BaseModel, EmailStr


class UserRead(BaseModel):
    id: int
    keycloak_id: str
    email: EmailStr
    name: str
    roles: list[str]

    model_config = {'from_attributes': True}
