import werkzeug
from flask import Flask, render_template, request, redirect, url_for, flash, g, abort
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, ForeignKey
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, EmailField, PasswordField
from flask_ckeditor import CKEditorField
from wtforms.validators import DataRequired, URL, InputRequired
from flask_ckeditor import CKEditor
import os
import datetime
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps
from typing import List
from bs4 import BeautifulSoup

app = Flask(__name__)
# app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SECRET_KEY'] = os.environ.get("blog_key")
ckeditor = CKEditor()

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

# class blog_post(db.Model):
#     id: Mapped[int] = mapped_column(primary_key=True)
#     title: Mapped[str] = mapped_column(unique=True)
#     author: Mapped[str] = mapped_column(unique=True)
#     date: Mapped[str] = mapped_column()
#     body: Mapped[str] = mapped_column()
#     url: Mapped[str] = mapped_column()
#     subtitle: Mapped[str] = mapped_column()
#
# # User model must inherit from UserMixin
# class User(UserMixin, db.Model):
#     id = db.Column(db.Integer, primary_key=True)
#     name = db.Column(db.String(150), unique=True)
#     email = db.Column(db.String)
#     password_hash = db.Column(db.String(256))

class User(UserMixin, db.Model):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150), unique=True)
    email: Mapped[str] = mapped_column(unique=True)
    password_hash: Mapped[str] = mapped_column(String(256))

    # Relationship to blog_post
    posts: Mapped[List["blog_post"]] = relationship(back_populates="author")
    comments: Mapped[List["Comments"]] = relationship(back_populates="author")

# blog_post → Child
class blog_post(db.Model):
    __tablename__ = "blog_posts"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(unique=True)
    date: Mapped[str] = mapped_column()
    body: Mapped[str] = mapped_column()
    url: Mapped[str] = mapped_column()
    subtitle: Mapped[str] = mapped_column()

    # Foreign Key to User
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    author: Mapped["User"] = relationship(back_populates="posts")

    comments: Mapped[List["Comments"]] = relationship(back_populates="post")

class Comments(db.Model):
    __tablename__ = "user_comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    comment: Mapped[str] = mapped_column()

    # Foreign Key to User
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    author: Mapped["User"] = relationship(back_populates="comments")

    post_id: Mapped[int] = mapped_column(ForeignKey("blog_posts.id"))
    post: Mapped["blog_post"] = relationship(back_populates="comments")

app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("blog_db_uri")
# app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///posts.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)

if not os.path.exists("posts.db"):
    with app.app_context():
        db.create_all()

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class Form(FlaskForm):
    title = StringField(label='Title', validators=[DataRequired()])
    url = StringField(label='URL', validators=[DataRequired()])
    subtitle = StringField(label='Subtitle', validators=[DataRequired()])
    body = CKEditorField(label='Body', validators=[DataRequired()])
    submit = SubmitField(label='Submit')

class RegForm(FlaskForm):
    name = StringField(label='Title', validators=[DataRequired()])
    email = EmailField(label='Author', validators=[DataRequired()])
    password_hash = PasswordField(label='URL', validators=[DataRequired()])
    submit = SubmitField(label='Submit')

class CommentForm(FlaskForm):
    comment = CKEditorField(label='Comment', validators=[DataRequired()])
    submit = SubmitField(label='Submit')

def create_app():
    ckeditor.init_app(app)
    return app

create_app()

@app.before_request
def load_logged_in_user():
    if current_user.is_authenticated:
        g.user = current_user  # This is a proxy for your user object
    else:
        g.user = None


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not g.user.id == 1:
            return abort(403)
        elif g.user.id and not g.user.id == 1:
            flash("Admin required")
        return f(*args, **kwargs)
    return decorated_function

@app.route("/")
def home():
    data = db.session.execute(db.select(blog_post).order_by(blog_post.id))
    db_posts = data.scalars().all()

    post_list = []

    for saved_post in db_posts:
        post_dict = {
            "id": saved_post.id,
            "title": saved_post.title,
            "date": saved_post.date,
            "url": saved_post.url,
            "body": saved_post.body,
            "subtitle": saved_post.subtitle,
            "author": saved_post.author
        }

        post_list.append(post_dict)

    return render_template("index.html", list=post_list, current_user=current_user)

@app.route("/post", methods=['POST', 'GET'])
def post():
    form = CommentForm()
    # print(secrets.token_hex(32))
    post_id = request.args.get("post_id")

    post_to_view = db.get_or_404(blog_post, post_id)

    comments_data = post_to_view.comments

    if form.is_submitted():
        form_content = form.comment.data

        soup = BeautifulSoup(form_content, "html.parser")
        plain_text = soup.get_text()

        comment_dict = {
            "comment": plain_text,
            "author_id": current_user.id,
            "post_id": post_id
        }

        new_comment = Comments(**comment_dict)
        db.session.add(new_comment)
        db.session.commit()

    return render_template("post.html", post=post_to_view, post_id=post_id, current_user=current_user, form=form, comments=comments_data)

@app.route("/create", methods=['POST', 'GET'])
@admin_required
def create():
    form = Form()

    if form.validate_on_submit():

        today = datetime.datetime.today()

        # Format
        formatted_date = today.strftime("%B %d, %Y")

        form_dict = {
            "title": form.title.data,
            "date": formatted_date,
            "url": form.url.data,
            "body": form.body.data,
            "subtitle": form.subtitle.data,
            "author_id": current_user.id
        }

        new_post = blog_post(**form_dict)
        db.session.add(new_post)
        db.session.commit()

        return redirect(url_for('home'))

    return render_template("create.html", form=form, current_user=current_user)

@app.route("/edit", methods=['POST', 'GET'])
@admin_required
def edit():
    post_id = request.args.get("post_id")

    post_to_edit = db.get_or_404(blog_post, post_id)

    form = Form(
        title=post_to_edit.title,
        url=post_to_edit.url,
        date=post_to_edit.date,
        subtitle=post_to_edit.subtitle,
        body=post_to_edit.body  # CKEditor content!
    )

    if form.validate_on_submit():

        today = datetime.datetime.today()

        # Format
        formatted_date = today.strftime("%B %d, %Y")

        post_to_edit.title = form.title.data
        post_to_edit.url = form.url.data
        post_to_edit.date = formatted_date
        post_to_edit.subtitle = form.subtitle.data
        post_to_edit.body = form.body.data
        db.session.commit()

        return redirect(url_for('home'))

    return render_template("edit.html", post_id=post_id, form=form, current_user=current_user)

@app.route("/delete", methods=["POST", "GET"])
@admin_required
def delete():
    post_id = request.args.get("post_id")

    if post_id and post_id.isdigit():
        post_id = int(post_id)
    else:
        return "Invalid item ID"

    if post_id:
        post_to_delete = db.session.execute(db.select(blog_post).where(blog_post.id == post_id)).scalar()
        db.session.delete(post_to_delete)
        db.session.commit()

    return home()

@app.route("/register", methods=['POST', 'GET'])
def register():
    form=RegForm()

    if form.validate_on_submit():

        password_hash = form.password_hash.data
        encrypted = werkzeug.security.generate_password_hash(password_hash, method='pbkdf2', salt_length=8)

        user_dict = {
            "name": form.name.data,
            "email": form.email.data,
            "password_hash": encrypted
        }

        user_exists = User.query.filter_by(email=form.email.data).first()
        print(user_exists)

        if user_exists:
            flash("You're already registered")
            return redirect(url_for('login', user=user_dict["name"]))

        else:
            new_user = User(**user_dict)
            print(new_user)
            db.session.add(new_user)
            db.session.commit()

            login_user(new_user)

        return redirect(url_for('home', user=user_dict["name"]))

    return render_template("register.html", form=form)

@app.route("/login", methods=['POST', 'GET'])
def login():
    form = RegForm()

    if request.method == 'POST':
        user = User.query.filter_by(email=form.email.data).first()

        if user:
            if check_password_hash(user.password_hash, form.password_hash.data):
                login_user(user)
                return redirect(url_for("home", user=user.name))

            else:
                flash('Incorrect Password')
                return render_template("login.html", form=form)

        else:
            flash('Account not found')

    return render_template("login.html", form=form)

@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("home"))

if __name__ == "__main__":
    app.run(debug=False)