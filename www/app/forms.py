#!/usr/bin/env python

from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, IntegerField, FieldList, FormField, SelectField
from wtforms.validators import ValidationError, DataRequired, NumberRange
from app.models import Entity, News, Art, References
from app import db
import sqlalchemy as sa


class CSRFExemptForm(FlaskForm):
    class Meta:
        csrf = False
# each subform within the FieldList is expecting its own CSRF token, 
# but the dynamically added fields don't have these tokens. 
# This issue arises because Flask-WTF generates a CSRF token for each subform instance when the form is rendered, 
# but when you add fields dynamically using JavaScript, they don’t automatically get the CSRF token


class HistItemForm(CSRFExemptForm):
    date  = StringField('date')
    stage = StringField('stage')


class EntityEditForm(FlaskForm):
    status = SelectField('status', choices=[
        ('live', 'live'),
        ('potential', 'potential'),
        ('disabled', 'disabled')])
    name          = StringField('name')
    stage_current = IntegerField('stage_current', validators=[NumberRange(min=1, max=4)])
    stage_history = FieldList(FormField(HistItemForm), min_entries=0, max_entries=10)
    stage_EM4view = IntegerField('stage_EM4view', validators=[NumberRange(min=1, max=4)])
    date_started  = StringField('date_started')
    date_ended    = StringField('date_ended')
    summary       = StringField('summary')
    corp_fam      = StringField('corp_fam')
    category = SelectField('category', choices=[
        ('None', 'None'),
        ('social', 'social'),
        ('cloud', 'cloud')])
    submit        = SubmitField('Submit Entity')
    def validate_required(self, name, stage_current, stage_EM4view):
        if not stage_EM4view:
            stage_EM4view = stage_current
        if not name or not stage_current:
            raise ValidationError('Status, name, stage_current, and stage_EM4view are required.')


# EntityAddForm is same as EntityEditForm except edit can use existing name whereas add can not use existing name
class EntityAddForm(EntityEditForm):
    def validate_name(self, name):
        name_choice = db.session.scalar(sa.select(Entity).where(Entity.name == name.data))
        if name_choice is not None:
            raise ValidationError('Please use a different name.')


class ListItemForm(CSRFExemptForm):
    item = StringField('Entity', validators=[DataRequired()])


class NewsForm(FlaskForm):
    date_pub  = StringField('date_pub')
    url       = StringField('URL')
    text      = StringField('text')
    summary   = StringField('summary')
    ent_names = FieldList(FormField(ListItemForm), min_entries=0, max_entries=10)
    submit    = SubmitField('Submit News')


class ArtForm(FlaskForm):
    date_pub  = StringField('date_pub')
    url       = StringField('URL', validators=[DataRequired()])
    text      = StringField('text', validators=[DataRequired()])
    summary   = StringField('summary')
    ent_names = FieldList(FormField(ListItemForm), min_entries=0, max_entries=10)
    submit    = SubmitField('Submit Art')


class ReferencesForm(FlaskForm):
    date_pub = StringField('date_pub')
    url      = StringField('URL', validators=[DataRequired()])
    text     = StringField('text', validators=[DataRequired()])
    summary  = StringField('summary')
    submit   = SubmitField('Submit Reference')


class SelectForm(FlaskForm):
    target_table = SelectField('target_table', choices=[
        ('Entity', 'Entity'),
        ('News', 'News'),
        ('Art', 'Art'),
        ('References', 'References')])
    target_id    = IntegerField('target_id')
    submit       = SubmitField('Submit Select')


class SelectAddForm(FlaskForm):
    target_table = SelectField('target_table', choices=[
        ('Entity', 'Entity'),
        ('News', 'News'),
        ('Art', 'Art'),
        ('References', 'References')])
    submit = SubmitField('Submit Select')

