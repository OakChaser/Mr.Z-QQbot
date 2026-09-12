from pydantic import BaseModel


class Config(BaseModel):
    forward_source_groups: list[int] = []
    sync_target_groups: list[int] = []