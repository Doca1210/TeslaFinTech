from pydantic import BaseModel


class EntityNameOut(BaseModel):
    name_type: str
    quality: str | None
    full_name: str

    class Config:
        from_attributes = True


class EntitySearchResult(BaseModel):
    id: int
    entity_type: str
    primary_name: str
    source_list: str
    programs: list[str]
    matched_names: list[EntityNameOut]

    class Config:
        from_attributes = True


class IngestionResult(BaseModel):
    source_list: str
    entries_processed: int
    publish_date: str | None
