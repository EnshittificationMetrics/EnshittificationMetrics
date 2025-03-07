from typing import Optional
import sqlalchemy as sa
import sqlalchemy.orm as so
from flask_login import UserMixin
from app import db, login
from sqlalchemy.ext.mutable import MutableList
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import Text
from datetime import datetime


class Entity(UserMixin, db.Model):
    id:            so.Mapped[int] = so.mapped_column(primary_key=True)
    status:        so.Mapped[str] = so.mapped_column(sa.String(10), default='potential') # live, potential, disabled
    name:          so.Mapped[str] = so.mapped_column(sa.String(64), index=True, unique=True)
    ent_url:       so.Mapped[str] = so.mapped_column(sa.String(70), nullable=True)
    seed:          so.Mapped[str] = so.mapped_column(sa.Text, nullable=True)
    stage_current: so.Mapped[int] = so.mapped_column(default='1')
    stage_history: so.Mapped[Optional[list]] = so.mapped_column(MutableList.as_mutable(sa.PickleType), default=[]) # each list item should be date and stage value, with hopefully a third, news item id
    stage_EM4view: so.Mapped[int] = so.mapped_column(default='2')
    date_started:  so.Mapped[str] = so.mapped_column(sa.String(10), default='')
    date_ended:    so.Mapped[str] = so.mapped_column(sa.String(10), default='current')
    summary:       so.Mapped[str] = so.mapped_column(sa.String(1024), nullable=True)
    corp_fam:      so.Mapped[str] = so.mapped_column(sa.String(64), nullable=True)
    category:      so.Mapped[str] = so.mapped_column(sa.String(64), nullable=True) # Social, Cloud, B2B, B2C, C2C, tech platform, P2P
    timeline:      so.Mapped[str] = so.mapped_column(sa.String(4096), nullable=True)
    data_map:      so.Mapped[str] = so.mapped_column(sa.Text, nullable=True)

    def __repr__(self):
        return '<Entity {}>'.format(self.name)


class News(UserMixin, db.Model):
    id:            so.Mapped[int] = so.mapped_column(primary_key=True)
    date_pub:      so.Mapped[str] = so.mapped_column(sa.String(10), default='')
    url:           so.Mapped[str] = so.mapped_column(sa.String(64), nullable=True)
    text:          so.Mapped[str] = so.mapped_column(sa.String(128), nullable=True)
    summary:       so.Mapped[str] = so.mapped_column(sa.String(1024), nullable=True)
    ent_names:     so.Mapped[Optional[list]] = so.mapped_column(MutableList.as_mutable(sa.PickleType), default=[])
    judgment:      so.Mapped[str] = so.mapped_column(sa.String(1024), nullable=True)
    stage_int_value: so.Mapped[int] = so.mapped_column(nullable=True)

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
    enable_notifications:    so.Mapped[Optional[bool]]     = so.mapped_column(sa.Boolean, default=False)
    last_sent:               so.Mapped[Optional[datetime]] = so.mapped_column(sa.DateTime, nullable=True)
    notification_frequency:  so.Mapped[Optional[str]]      = so.mapped_column(sa.String(10), nullable=True, default='weekly')
    alert_on_art_item:       so.Mapped[Optional[bool]]     = so.mapped_column(sa.Boolean, default=False)
    alert_on_reference_item: so.Mapped[Optional[bool]]     = so.mapped_column(sa.Boolean, default=False)
    categories_following:    so.Mapped[Optional[list]]     = so.mapped_column(MutableList.as_mutable(sa.PickleType), default=[])
    entities_following:      so.Mapped[Optional[list]]     = so.mapped_column(MutableList.as_mutable(sa.PickleType), default=[])
    alert_on_stage_change:   so.Mapped[Optional[bool]]     = so.mapped_column(sa.Boolean, default=False)
    alert_on_news_item:      so.Mapped[Optional[bool]]     = so.mapped_column(sa.Boolean, default=False)
    ai_suggestions:          so.Mapped[Optional[bool]]     = so.mapped_column(sa.Boolean, default=False)

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

int:          so.Mapped[int]                = so.mapped_column()
string:       so.Mapped[Optional[str]]      = so.mapped_column(sa.String(20), nullable=True)
float:        so.Mapped[Optional[float]]    = so.mapped_column()
list:         so.Mapped[Optional[list]]     = so.mapped_column(MutableList.as_mutable(sa.PickleType), default=[])
text:         so.Mapped[Optional[str]]      = so.mapped_column(Text, nullable=True) # larger blocks of text
boolean:      so.Mapped[Optional[bool]]     = so.mapped_column(sa.Boolean, default=False)
datetime_utc: so.Mapped[Optional[datetime]] = so.mapped_column(sa.DateTime, nullable=True)
"""


"""
To make changes to class(es):

pipenv shell
flask db init # onetime use!
flask db migrate -m "some change" # generates migration script; use in dev after change/addition to models.py
flask db upgrade # applies changes to the database; use in dev; only one need to run in prod, after pull of new models.py
"""
