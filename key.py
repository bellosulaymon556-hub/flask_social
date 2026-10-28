from flask import Flask, redirect, url_for, render_template, request, jsonify,send_from_directory,flash, session
import os
import datetime
import click
from flask import abort
from werkzeug.security import (generate_password_hash,check_password_hash)
from sqlalchemy import select
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from werkzeug.utils import secure_filename

def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    UPLOAD_FOLDER = os.path.join(os.getcwd(),'uploads')
    ALLOW_EXTENSIONS = {'png','jpg','jpeg','gif'}

    app.config.from_pyfile('config.py', silent=True)
    app.config.from_mapping(SECRET_KEY='dev')
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
    os.makedirs(UPLOAD_FOLDER, exist_ok = True)

    def allowed_file(filename):
        return'.' in filename and filename.rsplit('.',1)[1].lower() in ALLOW_EXTENSIONS

    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///event_database10.db"

    class Base(DeclarativeBase):
        pass

    db = SQLAlchemy(model_class=Base)
    db.init_app(app)

    class User(db.Model):
        id = mapped_column(db.Integer, primary_key=True)
        name = mapped_column(db.String(100), nullable=False)
        email = mapped_column(
            db.String(150), unique=True, nullable=False)
        password = mapped_column(db.String(255), nullable=False)
    class Comment(db.Model):
        id = mapped_column(db.Integer,primary_key=True)
        date = mapped_column(db.DateTime, default=datetime.datetime.now)
        content = mapped_column(db.Text,nullable=False)
        post_id = mapped_column(db.ForeignKey("post.id"),nullable=False)
        user_id = mapped_column(db.ForeignKey("user.id"),nullable=False)
        post = db.relationship("Post", back_populates="comments")
        user = db.relationship("User")

    class Post(db.Model):
        id = mapped_column(db.Integer, primary_key=True)
        date = mapped_column(db.DateTime, default=datetime.datetime.now)
        title = mapped_column(db.String(200), nullable=False)
        description = mapped_column(db.Text, nullable=False)
        image = mapped_column(db.String(500),nullable=False)
        image1 =mapped_column(db.String(500),nullable=False)
        user_id =mapped_column(db.ForeignKey("user.id"),nullable=True)
        comments = db.relationship("Comment",back_populates="post",cascade="all, delete-orphan")
    @click.command('init-db')
    def init_db_command():
        """Command for initializing the database"""
        with app.app_context():
            db.create_all()
            click.echo('Database created successfully')

    app.cli.add_command(init_db_command)

    @app.route("/signup", methods=["GET", "POST"])
    def signup():
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")

            if not name or not email or not password:
                flash("Please fill in every field.")
                return redirect(url_for("signup"))

            if len(password) < 8:
                flash("Password must be at least 8 characters.")
                return redirect(url_for("signup"))

            existing_user = db.session.execute(
                select(User).where(User.email == email)
            ).scalar_one_or_none()

            if existing_user:
                flash("This email is already registered.")
                return redirect(url_for("signup"))

            new_user = User(
                name=name,
                email=email,
                password=generate_password_hash(password)
            )

            db.session.add(new_user)
            db.session.commit()

            flash("Account created! Please log in.")
            return redirect(url_for("login"))

        return render_template("signup.html")



    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")

            user = db.session.execute(
                select(User).where(User.email == email)
            ).scalar_one_or_none()

            if user and check_password_hash(user.password, password):
                session.clear()
                session["user_id"] = user.id
                return redirect(url_for("home"))

            flash("Invalid email or password.")

        return render_template("login.html")


    @app.route('/uploads/<filename>')
    def uploaded_file(filename):
        return send_from_directory(UPLOAD_FOLDER,filename)

    @app.route('/', methods=['GET','POST'])
    def home():
        user = None

        if session.get("user_id"):
            user = db.session.get(User, session["user_id"])
        if request.method == 'POST':

            if 'post_photo' not in request.files:
                return 'no image uploaded'
            if 'post_photo2' not in request.files:
                return 'no image uploaded'

            may = request.files['post_photo']
            photo = request.files['post_photo2']

            if may.filename == '':
                return 'no file selected'
            if photo.filename == '':
                return 'no file selected'

            if may and allowed_file(may.filename):
                may_filename = secure_filename(may.filename)   
            if photo and allowed_file(photo.filename):
                photo_filename = secure_filename(photo.filename)   

                may.save(os.path.join(app.config['UPLOAD_FOLDER'],may_filename))
                photo.save(os.path.join(app.config['UPLOAD_FOLDER'],photo_filename))

            else:
                return'File extension not allowed'

            new_post = Post(
                 title=request.form['title'],
                 description=request.form['description'],
                 image=may_filename,
                 image1=photo_filename,
                 user_id=user.id
            )

            db.session.add(new_post)
            db.session.commit()
            return redirect(url_for('home'))
        if session.get("user_id"):
            user = db.session.get(User, session["user_id"])

        postslist=db.session.execute(db.select(Post).order_by(Post.date.desc())).scalars().all()
        return render_template('primary.html',postslist=postslist,user=user)

    @app.route('/api/create', methods=['POST'])
    def create():
        if request.method == 'POST':
            title=request.form['title']
            description=request.form['description']

            if title == '' or description == '':
                return "missing required field"
            new_post = Post( 
                 title=title,
                 description=description
            )
            db.session.add(new_post)
            db.session.commit()
            # return redirect(url_for('home'))
            return db.session.execute(db.select(Post).order_by(Post.date)).scalars()

    @app.route('/post/<id>', methods=['GET','POST'])
    def show_user(id):
        # return f'Hello {username} !'
        post = Post.query.get(id)

        if request.method == 'POST':
            post.title = request.form['title']
            post.description = request.form['description']

            db.session.commit()
            return redirect(url_for('show_user', id=post.id))

        return render_template('post.html', post=post)

    @app.route('/edit/<id>', methods=['GET','POST'])
    def edit_post(id):
        edit = Post.query.get(id)

        if request.method == 'POST':
            if 'post_image' not in request.files:
                return 'no image uploaded'
            if 'post_image1' not in request.files:
                return 'no image uploaded'

            nysc = request.files['post_image']
            nerd = request.files['post_image1']

            if nysc.filename == '':
                return 'no file selected'

            if nerd.filename == '':
                return 'no file selected'

            if nysc and allowed_file(nysc.filename):
                nysc_filename = secure_filename(nysc.filename)

            if nerd and allowed_file(nerd.filename):
                nerd_filename = secure_filename(nerd.filename)

                nysc.save(os.path.join(app.config['UPLOAD_FOLDER'], nysc_filename))
                nerd.save(os.path.join(app.config['UPLOAD_FOLDER'], nerd_filename))

            edit.title = request.form['title']
            edit.description = request.form['description']
            edit.image = nysc_filename
            edit.image1 = nerd_filename

            db.session.commit()
            return redirect(url_for('home'))

        else:
            edit = Post.query.get(id)
            return render_template('edit.html', edit=edit)
            return redirect(url_for("home"))

    @app.route("/post/<int:post_id>/comment", methods=["POST"])
    def add_comment(post_id):
        if not session.get("user_id"):
            return redirect(url_for("login"))

        user = db.session.get(User, session["user_id"])
        post = db.session.get(Post, post_id)

        if not user or not post:
            abort(404)

        content = request.form.get("content", "").strip()

        if not content:
            flash("Please write a comment.")
            return redirect(url_for("home"))

        new_comment = Comment(
            content=content,
            post_id=post.id,
            user_id=user.id
        )

        db.session.add(new_comment)
        db.session.commit()

        return redirect(url_for('home'))

    @app.route('/delete/<id>', methods=['GET','POST'])
    def delete_post(id):
        if not session.get("user_id"):
            return redirect(url_for("login"))

        user = db.session.get(User, session["user_id"])
        post = db.session.get(Post, id)

        if not post:
            abort(404)

        if post.user_id != user.id:
            abort(403)

        db.session.delete(post)
        db.session.commit()

        return redirect(url_for('home'))

    @app.route('/upload', methods=['GET','POST'])
    def upload_post():
        if request.method == "POST":

            if 'post_image' not in request.files:
                return 'no image uploaded'
            if 'post_image1' not in request.files:
                return 'no image uploaded'

            nysc = request.files['post_image']
            nerd = request.files['post_image1']

            if nysc.filename == '':
                return 'no file selected'

            if nerd.filename == '':
                return 'no file selected'

            if nysc and allowed_file(nysc.filename):
                nysc_filename = secure_filename(nysc.filename)

            if nerd and allowed_file(nerd.filename):
                nerd_filename = secure_filename(nerd.filename)

                nysc.save(os.path.join(app.config['UPLOAD_FOLDER'], nysc_filename))
                nerd.save(os.path.join(app.config['UPLOAD_FOLDER'], nerd_filename))

                return f'nysc"{nysc_filename}" and nerd"{nerd_filename}" uploaded successfully!'
            return'File extension not allowed'

        return render_template('upload.html')

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)