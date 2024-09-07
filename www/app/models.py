from typing import Optional
import sqlalchemy as sa
import sqlalchemy.orm as so
from flask_login import UserMixin
from app import db
from sqlalchemy.ext.mutable import MutableList


class Entity(UserMixin, db.Model):
    id:            so.Mapped[int] = so.mapped_column(primary_key=True)
    status:        so.Mapped[str] = so.mapped_column(sa.String(10), default='potential') # live, potential, disabled
    name:          so.Mapped[str] = so.mapped_column(sa.String(64), index=True, unique=True)
    stage_current: so.Mapped[int] = so.mapped_column(default='1')
    stage_history: so.Mapped[Optional[list]] = so.mapped_column(MutableList.as_mutable(sa.PickleType), default=[]) # each list item should be date and stage value pair
    stage_EM4view: so.Mapped[int] = so.mapped_column(default='2')
    date_started:  so.Mapped[str] = so.mapped_column(sa.String(10), default='')
    date_ended:    so.Mapped[str] = so.mapped_column(sa.String(10), default='current')
    summary:       so.Mapped[str] = so.mapped_column(sa.String(1024), nullable=True)
    corp_fam:      so.Mapped[str] = so.mapped_column(sa.String(64), nullable=True)
    category:      so.Mapped[str] = so.mapped_column(sa.String(64), nullable=True) # social, cloud

    def __repr__(self):
        return '<Entity {}>'.format(self.name)


class News(UserMixin, db.Model):
    id:            so.Mapped[int] = so.mapped_column(primary_key=True)
    date_pub:      so.Mapped[str] = so.mapped_column(sa.String(10), default='')
    url:           so.Mapped[str] = so.mapped_column(sa.String(64), nullable=True)
    text:          so.Mapped[str] = so.mapped_column(sa.String(128), nullable=True)
    summary:       so.Mapped[str] = so.mapped_column(sa.String(1024), nullable=True)
    ent_names:     so.Mapped[Optional[list]] = so.mapped_column(MutableList.as_mutable(sa.PickleType), default=[])

    def __repr__(self):
        return '<News {}>'.format(self.text)


class Art(UserMixin, db.Model):
    id:            so.Mapped[int] = so.mapped_column(primary_key=True)
    date_pub:      so.Mapped[str] = so.mapped_column(sa.String(10), default='')
    url:           so.Mapped[str] = so.mapped_column(sa.String(64), nullable=True)
    text:          so.Mapped[str] = so.mapped_column(sa.String(128), nullable=True)
    summary:       so.Mapped[str] = so.mapped_column(sa.String(1024), nullable=True)
    ent_names:     so.Mapped[Optional[list]] = so.mapped_column(MutableList.as_mutable(sa.PickleType), default=[])

    def __repr__(self):
        return '<Art {}>'.format(self.text)


class References(UserMixin, db.Model):
    id:            so.Mapped[int] = so.mapped_column(primary_key=True)
    date_pub:      so.Mapped[str] = so.mapped_column(sa.String(10), default='')
    url:           so.Mapped[str] = so.mapped_column(sa.String(64), nullable=True)
    text:          so.Mapped[str] = so.mapped_column(sa.String(128), nullable=True)
    summary:       so.Mapped[str] = so.mapped_column(sa.String(1024), nullable=True)

    def __repr__(self):
        return '<References {}>'.format(self.text)


# to make changes to class(es):
# pipenv shell
# flask db init # onetime use!
# flask db migrate -m "some change" # generates migration script
# flask db upgrade # applys changes to the database
