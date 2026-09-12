from pydantic import BaseModel


class Config(BaseModel):
    greeting_targets: list[str] = []
    greeting_test_time: str = ""