from venv import create
from modules import app, login_manager, bcrypt
from models import Job, User, db, create_tables
from flask import render_template, redirect, url_for
import json, os, datetime, markdown
from flask_login import login_user, login_required, logout_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import InputRequired, Length, ValidationError
from api import *


REGISTER_URL = os.environ.get('REGISTER_URL')

if not os.path.exists('jobs.db'):
    f = open('jobs.db', 'w')
    f.close()
    create_tables()

with open('static/site.config.json', 'r') as f:
    site_data = json.load(f)

def is_sytem_admin(Uemail):
    for email in site_data['system_administrators']:
        if email == Uemail:
            return True

def has_posting_expired(job):
    return job.date_expiry < datetime.datetime.now()

ACCESS_TOKEN = os.environ.get('ACCESS_TOKEN')

"""
When the user enters the page they land on the email wall
- If the email is in the database, they are redirected to the job listings page
"""
class RegisterForm(FlaskForm):
    password = PasswordField(validators=[InputRequired(), Length(min=4, max=20)])
    email = StringField(validators=[InputRequired(), Length(min=4, max=30)])
    submit = SubmitField("Register")
    
    def validate_email(self, email):
        exisiting_email = User.query.filter_by(email=email.data).first()
        if exisiting_email:
            raise ValidationError("That email already exists. Please choose a different one ")

class LoginForm(FlaskForm):
    email = StringField(validators=[InputRequired(), Length(min=4, max=30)])
    password = PasswordField(validators=[InputRequired(), Length(min=4, max=20)])
    submit = SubmitField("Login")

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@login_required
@app.route('/')
def index():
    return render_template('index.html', config=site_data)

@app.route('/jobs/<int:job_id>', methods=['GET'])
def job_detail(job_id):
    job = Job.query.filter_by(id=job_id).first()
    job.content = markdown.markdown(job.content)
    if job:
        if has_posting_expired(job):
            return render_template('job_detail.html', config=site_data, job=job, expired=True)
        else:
            return render_template('job_detail.html', config=site_data, job=job)
    else:
        return render_template('job_detail.html', config=site_data, job=None)

@app.route('/login/', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    errors = []
    
    if current_user.is_authenticated:
        if current_user.isAdmin:
            return redirect(url_for('dashboard'))
        return redirect(url_for('index'))

    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            if bcrypt.check_password_hash(user.password, form.password.data):
                login_user(user)
                if user.isAdmin:
                    return redirect(url_for('dashboard'))
                else:
                    return redirect(url_for('index'))
            else:
                errors.append("You have entered an invalid password, please try again")
        else:
            errors.append("You have entered an invalid email, please try again")
    else:
        errors.append(form.errors)
    
    # bandage fix to error page
    errors = [] if str(errors) == "[{}]" else errors

    return render_template('login.html', form=form , config=site_data, errors=errors)

@app.route('/logout/')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route(f'/{REGISTER_URL}/', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    errors = None
    
    if current_user.is_authenticated:
        if current_user.isAdmin:
            return redirect(url_for('dashboard'))
        else:
            return redirect(url_for('index'))

    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data)
        if is_sytem_admin(form.email.data):
            user = User(email=form.email.data, password=hashed_password, isAdmin=True)
            db.session.add(user)
        else:
            user = User(email=form.email.data, password=hashed_password, isAdmin=False)
            db.session.add(user)
        
        db.session.commit()
        return redirect(url_for('login'))
    else:
        errors = form.errors
    return render_template('register.html', form=form, config=site_data, errors=errors)

@login_required
@app.route('/config/', methods=['GET'])
def site_config():
    if current_user.isAdmin:
        return render_template('config.html', config=site_data, fconfig=json.dumps(site_data, indent=2))
    else:
        return redirect(url_for('index'))

@app.route('/dashboard/', methods=['GET'])
@login_required
def dashboard():
    if current_user.isAdmin:
        return render_template('dashboard.html', config=site_data)
    else:
        return redirect(url_for('index'))

@app.route('/expired_jobs/', methods=['GET'])
@login_required
def expired_jobs():
    if current_user.isAdmin:
        jobs = Job.query.all()
        jobs = [job for job in jobs if has_posting_expired(job)]
        return render_template('expired_jobs.html', config=site_data, jobs=jobs, expired=True)
    else:
        return redirect(url_for('index'))

# Error Handling
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html', config=site_data), 404

@login_manager.unauthorized_handler
def unauthorized_handler():
    return redirect(url_for('index'))