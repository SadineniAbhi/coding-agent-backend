from beanie import Document
from pymongo import IndexModel


class user(Document):
    user_id: str
    installation_id: str

    class Settings:
        indexes = [
            IndexModel([("user_id", 1)]),
        ]

