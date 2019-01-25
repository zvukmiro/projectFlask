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

# User searches for books (non isbn search and particular isbn search: could have one or more results)


@app.route("/books", methods=['GET', 'POST'])
def books():
    books = None
    if request.method == "POST":
        isbn = request.form.get("isbn")
        title = request.form.get("title")
        author = request.form.get("author")
        if isbn:
            books = db.execute("SELECT * FROM books WHERE isbn=:isbn", {"isbn": isbn})
            if books.rowcount == 0:
                books = db.execute(
                    "SELECT * FROM books WHERE isbn LIKE :isbn LIMIT 60", {"isbn": isbn+'%'})
        elif title and author:
            books = db.execute(
                "SELECT * FROM books WHERE author=:author AND title=:title LIMIT 30", {"author": author, "title": title})
        elif title:
            books = db.execute("SELECT * FROM books WHERE title=:title LIMIT 30", {"title": title})
            if books.rowcount == 0:
                books = db.execute(
                    "SELECT * FROM books WHERE title LIKE :title LIMIT 60", {"title": '%'+title+'%'})
        elif author:
            books = db.execute(
                "SELECT * FROM books WHERE author=:author LIMIT 30", {"author": author})
            if books.rowcount == 0:
                books = db.execute(
                    "SELECT * FROM books WHERE author LIKE :author LIMIT 60", {"author": '%'+author+'%'})
        db.close()
    return render_template("books.html", books=books)


@app.route("/books/<isbn>")
def book(isbn):
    session['isbn'] = isbn
    try:
        book = db.execute("SELECT * FROM books WHERE isbn=:isbn", {"isbn": isbn})
    except:
        flash("The book with isbn, or title/author entered not found in the database.")
        return redirect(url_for('error'))
    else:
        reviews = db.execute(
            "SELECT ROUND(AVG(rating), 1) FROM reviews WHERE rw_isbn=:isbn", {"isbn": isbn})
        if reviews.rowcount == 1:
            review = reviews.first()[0]
        res = requests.get("https://www.goodreads.com/book/review_counts.json",
                           params={"key": "SlE9tBsqoV9Pzyb7ENbHXg", "isbns": isbn})
        review2 = (res.json())['books'][0]['average_rating']
        return render_template("book.html", book=book, review=review, review2=review2)
    finally:
        db.close()


@app.route("/review", methods=['GET', 'POST'])
def review():
    if request.method == "POST":
        isbn = session['isbn']
        username = session['username']
        review = request.form.get("review")
        if (review.isdigit() or review.replace('.', '').isdigit()) and (float(review) > 0.99 and float(review) < 5.1):
            try:
                result = db.execute(
                    "SELECT * FROM reviews WHERE rw_user=:username AND rw_isbn=:isbn", {"username": username, "isbn": isbn})
                if (result.rowcount) > 0:
                    flash("Duplicate review for the same book not accepted.")
                    return redirect(url_for('error'))
                review = float(review)
                session['review'] = review
                res = db.execute("INSERT INTO reviews (rw_isbn, rw_user, rating) VALUES (:bookNum, :person, :numb)", {
                                 "bookNum": isbn, "person": username, "numb": review})
                db.commit()
                reviewCnt = db.execute(
                    "SELECT * FROM reviews WHERE rw_user=:username", {"username": username})
                return redirect(url_for('success'))
            except:
                flash("Your review did not post.")
                return redirect(url_for('error'))
        else:
            flash('The review is 1 to 5 stars. Please enter numbers btw 1.0 and 5.0.')
            return redirect(url_for('error'))

    return redirect(url_for('error'))


@app.route("/success")
def success():
    username = session['username']
    isbn = session['isbn']
    review = session['review']
    return render_template("success.html", username=username, isbn=isbn, review=review)


@app.route("/error")
def error():
    return render_template("error.html")
