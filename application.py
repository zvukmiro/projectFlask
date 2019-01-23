import os
import requests

from flask import Flask, session, render_template, request, redirect, url_for, logging, flash
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

from wtforms import Form, StringField, TextAreaField, PasswordField, validators
from passlib.hash import bcrypt
from functools import wraps

app = Flask(__name__)
app.secret_key = b'a1\xa4Q\xdev\xd7\x94\x1f\xac\x8an\x07\x98q\xdf'

# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))


# home page with a possibility to register or log in
@app.route("/")
def index():
    return render_template("index.html")

# Register Form Class


class RegisterForm(Form):
    username = StringField('Username', [validators.Length(min=4, max=25)])
    password = PasswordField('Password', [validators.Length(min=6, max=15)])


# User Register
@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm(request.form)
    if request.method == 'POST' and form.validate():
        username = form.username.data
        password = bcrypt.encrypt(str(form.password.data))
        if username and password:
            username = username.lower()
            # checking if there is the same username in db
            if (db.execute("SELECT * FROM users WHERE username=:username", {"username": username})).rowcount == 0:
                db.execute("INSERT INTO users (username, password) VALUES (:username, :password)", {
                           "username": username, "password": password})
                db.commit()
            else:
                message = "Username already exists, please choose different username."
                return render_template('register.html', form=form, message=message)
            flash('You are now registered, please login', 'success')
            return redirect(url_for('login'))
        else:
            message = "Need to input both username and password."
            return render_template('register.html', form=form, message=message)
    return render_template('register.html', form=form)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get("username")
        password = str(request.form.get("password"))
        if username and password:
            username = username.lower()
            result = db.execute("SELECT * FROM users WHERE username=:username",
                                {"username": username})
            if result.rowcount == 1 and bcrypt.verify(password, result.first()[2]):
                session['logged_in'] = True
                session['username'] = username
                return redirect(url_for('books'))
            else:
                flash('Username and password do not match. Please try again.')
        else:
            flash('Need to input both username and password. Please try again.')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('index'))
