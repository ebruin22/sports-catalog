# configuration code -import modules needed, beginning of file and eof
# class code - our data in python
# table code -represents a specific table in database
# mapper - connects columns of table to class that represents the table

# configuration code
# function used to control the runtime
import os
import sys

from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy import create_engine

# Need to set up variable that stores all features of sqlalchemy
# Will be used by classes to inherit all features
Base = declarative_base()


class User(Base):
    __tablename__ = 'user'

    # mapper code
    name = Column(
        String(250), nullable=False)
    id = Column(
        Integer, primary_key=True)
    email = Column(String(250), nullable=False)
    picture = Column(String(250))


# class code
# corresponds to restaurants table
class Category(Base):
    # table code
    # establish variable used to refer to table
    __tablename__ = 'category'

    # mapper code
    # columns in table
    name = Column(
        String(80), nullable=False)
    id = Column(
        Integer, primary_key=True)
    # type= Column(String(250))

    user_id = Column(Integer, ForeignKey('user.id'))
    user = relationship(User)

    @property
    def serialize(self):
        # Returns object data in easily serializeable format
        return {
            'name': self.name,
            # 'restaurant type': self.r_type,
            'id': self.id,
        }


# class code
# corresponds to menu items table
class Item(Base):
    # table code
    __tablename__ = 'item'

    # mapper code
    name = Column(
        String(80), nullable=False)
    id = Column(
        Integer, primary_key=True)
    # course = Column(String(250))
    image = Column(String(250))
    description = Column(String(250))
    price = Column(String(8))
    category_id = Column(
        Integer, ForeignKey('category.id'))
    # stores the relationship with class Restuarant
    # need it when use a foreign key relationship
    category = relationship(Category)

    user_id = Column(Integer, ForeignKey('user.id'))
    user = relationship(User)

    @property
    def serialize(self):
        # Returns object data in easily serializeable format
        return {
            'name': self.name,
            'description': self.description,
            'id': self.id,
            'price': self.price,
            # 'course': self.course,
        }


# config code
# end of file
engine = create_engine(
    'sqlite:///inventory.db')

Base.metadata.create_all(engine)
