from utils.database import metadata
from sqlalchemy import Table, Column, Integer, String, ForeignKey, Boolean, DateTime

expense_opponents_table = Table(
    'expense_opponents',
    metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('name', String(255), nullable=False),
    Column('type', String(50), nullable=False),
    Column('description', String(500), nullable=True),
    Column('paymentNumber', String(50), nullable=True),
    Column("npwp", String(16), nullable=True, default=None),
    Column('createdAt', DateTime(), nullable=False),
    Column('createdBy', Integer, ForeignKey('users.id'), nullable=False),
    Column('updatedAt', DateTime(), nullable=True, default=None),
    Column('updatedBy', Integer, ForeignKey('users.id'), nullable=True, default=None),
    Column('isDelete', Boolean, default=False),
    Column('deletedAt', DateTime(), nullable=True, default=None),
    Column('deletedBy', Integer, ForeignKey('users.id'), nullable=True, default=None),
)