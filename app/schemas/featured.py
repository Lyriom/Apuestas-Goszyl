from datetime import datetime

from pydantic import BaseModel, Field


class FeaturedContentEncryptedIn(BaseModel):
    post_id: int = Field(gt=0)
    ciphertext: str = Field(min_length=10)


class FeaturedPlaintext(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    excerpt: str = Field(min_length=1, max_length=2000)
    content_html: str = Field(min_length=1)
    slug: str = Field(min_length=1, max_length=260)


class FeaturedContentRead(BaseModel):
    id: int
    post_id: int
    title: str
    excerpt: str
    content_html: str
    slug: str
    received_at: datetime
    updated_at: datetime

    model_config = {'from_attributes': True}
