from sqlalchemy.orm import Session
from ..database.models import User
from ..database.schemas import UserCreate, UserUpdate
from typing import Optional, List

class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, uid: str) -> Optional[User]:
        return self.db.query(User).filter(User.uid == uid).first()

    def get_by_email(self, email: str) -> Optional[User]:
        return self.db.query(User).filter(User.email == email).first()

    def create(self, user_in: UserCreate) -> User:
        db_user = User(**user_in.model_dump())
        self.db.add(db_user)
        self.db.commit()
        self.db.refresh(db_user)
        return db_user

    def update(self, uid: str, user_in: UserUpdate) -> Optional[User]:
        db_user = self.get_by_id(uid)
        if not db_user:
            return None
        
        update_data = user_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_user, field, value)
        
        self.db.commit()
        self.db.refresh(db_user)
        return db_user

    def list(self, skip: int = 0, limit: int = 100) -> List[User]:
        return self.db.query(User).offset(skip).limit(limit).all()
