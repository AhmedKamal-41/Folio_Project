from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.config import MAX_CONTENT_CHARACTERS, MAX_CONTENT_OPERATIONS


class DocumentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(default="Untitled document", max_length=120)
    content: dict = Field(default_factory=lambda: {"ops": [{"insert": "\n"}]})

    @field_validator("title")
    @classmethod
    def validate_title(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Title cannot be empty.")
        return value

    @field_validator("content")
    @classmethod
    def validate_content(cls, value):
        ops = value.get("ops")
        if set(value) != {"ops"} or not isinstance(ops, list) or not 1 <= len(ops) <= MAX_CONTENT_OPERATIONS:
            raise ValueError("Content must contain between 1 and 5,000 text operations.")
        length = 0
        for operation in ops:
            if not isinstance(operation, dict) or set(operation) - {"insert", "attributes"}:
                raise ValueError("Invalid text operation.")
            if not isinstance(operation.get("insert"), str):
                raise ValueError("Only text content is supported.")
            length += len(operation["insert"])
            attributes = operation.get("attributes", {})
            if not isinstance(attributes, dict):
                raise ValueError("Invalid formatting.")
            for name, setting in attributes.items():
                if name in ("bold", "italic", "underline") and type(setting) is bool:
                    continue
                if name == "header" and type(setting) is int and setting in (1, 2, 3):
                    continue
                if name == "list" and isinstance(setting, str) and setting in ("bullet", "ordered"):
                    continue
                raise ValueError("Unsupported formatting.")
        if length > MAX_CONTENT_CHARACTERS or not ops[-1]["insert"].endswith("\n"):
            raise ValueError("Content must end with a newline and fit within 100,000 characters.")
        return value



class DocumentUpdate(DocumentCreate):
    version: int = Field(ge=1)



class ShareCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: int = Field(ge=1)



class UserResponse(BaseModel):
    id: int
    name: str
    email: str


class DocumentSummary(BaseModel):
    id: int
    title: str
    owner_id: int
    owner_name: str
    version: int
    updated_at: str


class DocumentResponse(DocumentSummary):
    content: dict
