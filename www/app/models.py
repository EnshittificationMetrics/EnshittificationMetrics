from typing import Optional
import sqlalchemy as sa
import sqlalchemy.orm as so
from flask_login import UserMixin
from app import db, login
from sqlalchemy.ext.mutable import MutableList
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import Text


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


class User(UserMixin, db.Model):
    id:            so.Mapped[int] = so.mapped_column(primary_key=True)
    username:      so.Mapped[str] = so.mapped_column(sa.String(64), index=True, unique=True)
    email:         so.Mapped[str] = so.mapped_column(sa.String(120), index=True, unique=True)
    password_hash: so.Mapped[Optional[str]] = so.mapped_column(sa.String(256))
    full_name:     so.Mapped[Optional[str]] = so.mapped_column(sa.String(120), default='')
    phone_number:  so.Mapped[Optional[str]] = so.mapped_column(sa.String(20), nullable=True)
    role:          so.Mapped[Optional[str]] = so.mapped_column(sa.String(64), default='regular')
    #              "guest" - auto logged on as if no account specified; limited accesses
    #              "regular" - default value for new account creations
    #              "administrator" - gets into "dev" routes
    #              "disabled" - denied any login
    validations:   so.Mapped[Optional[str]] = so.mapped_column(sa.String(64), default='')
    #              '', 'email', figure out sms/txt and/or multiple later...
    last_access:   so.Mapped[Optional[str]] = so.mapped_column(sa.String(11), default='')
    func_stage:    so.Mapped[int] = so.mapped_column(default = 1)
    #              To view/use site in; Stage 1 ~ Stage 2 ~ Stage 3 ~ Stage 4
    per_page:      so.Mapped[int] = so.mapped_column(default = 20)
    #              20, 50, etc.
    display_order: so.Mapped[str] = so.mapped_column(sa.String(16), default='recent first')
    #              recent first, oldest first
    ranking_sort:  so.Mapped[str] = so.mapped_column(sa.String(10), default='Stage')
    #              Alpha ~ by Stage ~ by Age
    ranking_cats:  so.Mapped[str] = so.mapped_column(sa.String(16), default='All')
    #              All, Social, Cloud, B2B, B2C, C2C, tech platform, P2P
    ranking_stat:  so.Mapped[str] = so.mapped_column(sa.String(10), default='Live')
    #              Live, Potential, Not Disabled, Disabled
    viewing_mode:  so.Mapped[str] = so.mapped_column(sa.String(10), default='light')
    #              light, dark
    to_view:       so.Mapped[str] = so.mapped_column(sa.String(4), default='XXXX')
    #              checkbox 1, 2, 3, and/or, 4 stages to view; XXXX

    def __repr__(self):
        return '<User {}>'.format(self.username)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


@login.user_loader
def load_user(id):
    return db.session.get(User, int(id))


class SurveyNewUser(UserMixin, db.Model):
    id:            so.Mapped[int] = so.mapped_column(primary_key=True)
    discovery:     so.Mapped[Optional[str]] = so.mapped_column(Text, nullable=True)
    thoughts:      so.Mapped[Optional[str]] = so.mapped_column(Text, nullable=True)
    suggestions:   so.Mapped[Optional[str]] = so.mapped_column(Text, nullable=True)
    monetization:  so.Mapped[Optional[str]] = so.mapped_column(Text, nullable=True)
    datetime:      so.Mapped[str] = so.mapped_column(sa.String(20), nullable=True)
    username:      so.Mapped[str] = so.mapped_column(sa.String(64), nullable=True)

    def __repr__(self):
        return '<SurveyNewUser {}>'.format(self.text)

"""
References:

int:    so.Mapped[int] = so.mapped_column()
string: so.Mapped[Optional[str]] = so.mapped_column(sa.String(20), nullable=True)
float:  so.Mapped[Optional[float]] = so.mapped_column()
list:   so.Mapped[Optional[list]] = so.mapped_column(MutableList.as_mutable(sa.PickleType), default=[])
text:   so.Mapped[Optional[str]] = so.mapped_column(Text, nullable=True) # larger blocks of text
"""


"""
To make changes to class(es):

pipenv shell
flask db init # onetime use!
flask db migrate -m "some change" # generates migration script; use in dev after change/addition to models.py
flask db upgrade # applies changes to the database; use in dev; only one need to run in prod, after pull of new models.py
"""
