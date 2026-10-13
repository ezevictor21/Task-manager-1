"""Task Manager - Flask application.

Routes
------
/                       public home page
/register, /login, /logout
/tasks                  dashboard (filter by status/priority, search, sort)
/tasks/new              create a task
/tasks/<id>/edit        update a task
/tasks/<id>/delete      delete a task (POST only)
/tasks/<id>/toggle      quick-complete / reopen a task (POST only)
/tasks/export           download the current user's tasks as CSV
/api/tasks              JSON list of the current user's tasks (session auth)

The app is built with an application factory (``create_app``) so the test
suite can spin up an isolated instance with an in-memory database.
"""

import csv
import io
from functools import wraps

from flask import (
    Flask,
    Response,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError

from config import Config
from models import PRIORITIES, STATUSES, Task, User, bcrypt, db
from validators import today_iso, validate_login, validate_registration, validate_task

SORTABLE_COLUMNS = {
    "due_date": Task.due_date,
    "title": Task.title,
    "status": Task.status,
    "priority": Task.priority,
    "created_at": Task.created_at,
}


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def login_required(view):
    """Redirect to the login page when no user is in the session."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


def current_user_id():
    """Return the id of the logged-in user (routes using this are protected)."""
    return session["user_id"]


def get_owned_task_or_404(task_id):
    """Fetch a task that belongs to the logged-in user, or abort with 404.

    Using 404 rather than 403 avoids revealing that another user's task
    exists.
    """
    task = db.session.get(Task, task_id)
    if task is None or task.user_id != current_user_id():
        abort(404)
    return task


def flash_errors(errors):
    """Flash each validation message as a 'danger' alert."""
    for message in errors:
        flash(message, "danger")


def normalize_choice(value, choices, *, default=None):
    """Return the canonical choice for a case-insensitive match, else the default."""
    if value is None:
        return default

    cleaned = (value or "").strip()
    if not cleaned:
        return default

    lowered = cleaned.lower()
    for choice in choices:
        if choice.lower() == lowered:
            return choice
    return default


# --------------------------------------------------------------------------- #
# Application factory
# --------------------------------------------------------------------------- #
def create_app(config_object=Config):
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.config.from_object(config_object)

    db.init_app(app)
    bcrypt.init_app(app)

    with app.app_context():
        db.create_all()

    register_routes(app)
    register_error_handlers(app)

    @app.context_processor
    def inject_constants():
        """Make the allowed status/priority values available to templates."""
        return {"STATUSES": STATUSES, "PRIORITIES": PRIORITIES}

    return app


def register_error_handlers(app):
    """Friendly pages for 404 and 500, and a rollback on database errors."""

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("404.html"), 404

    @app.errorhandler(500)
    def server_error(_error):
        db.session.rollback()
        return render_template("500.html"), 500


def register_routes(app):
    """Attach all view functions to ``app``."""

    # ------------------------------------------------------------------ #
    # Public pages
    # ------------------------------------------------------------------ #
    @app.route("/")
    def index():
        """Public landing page."""
        return render_template("index.html")

    # ------------------------------------------------------------------ #
    # Authentication
    # ------------------------------------------------------------------ #
    @app.route("/register", methods=["GET", "POST"])
    def register():
        """Create a new account after validating the submitted form."""
        if "user_id" in session:
            return redirect(url_for("dashboard"))

        if request.method == "POST":
            data, errors = validate_registration(request.form)

            if not errors:
                username_lookup = data["username"].lower()
                email_lookup = data["email"].lower()
                if User.query.filter(func.lower(User.username) == username_lookup).first():
                    errors.append("That username is already taken.")
                if User.query.filter(func.lower(User.email) == email_lookup).first():
                    errors.append("That email is already registered.")

            if errors:
                flash_errors(errors)
                return render_template("register.html", form=data), 400

            user = User(username=data["username"], email=data["email"])
            user.set_password(data["password"])
            try:
                db.session.add(user)
                db.session.commit()
            except SQLAlchemyError:
                db.session.rollback()
                flash("Registration failed. Please try again.", "danger")
                return render_template("register.html", form=data), 500

            flash("Registration successful! Please log in.", "success")
            return redirect(url_for("login"))

        return render_template("register.html", form={})

    @app.route("/login", methods=["GET", "POST"])
    def login():
        """Log a user in and start a session."""
        if "user_id" in session:
            return redirect(url_for("dashboard"))

        if request.method == "POST":
            data, errors = validate_login(request.form)
            user = None
            if not errors:
                username_lookup = data["username"].lower()
                user = User.query.filter(func.lower(User.username) == username_lookup).first()
                if user is None or not user.check_password(data["password"]):
                    errors.append("Invalid username or password.")

            if errors:
                flash_errors(errors)
                return render_template("login.html", form=data), 401

            session.clear()
            session["user_id"] = user.id
            session["username"] = user.username
            session.permanent = True
            flash(f"Welcome back, {user.username}!", "success")

            next_page = request.args.get("next")
            if next_page and next_page.startswith("/") and not next_page.startswith("//"):
                return redirect(next_page)
            return redirect(url_for("dashboard"))

        return render_template("login.html", form={})

    @app.route("/logout")
    def logout():
        """Clear the session."""
        session.clear()
        flash("You have been logged out.", "info")
        return redirect(url_for("index"))

    # ------------------------------------------------------------------ #
    # Task dashboard and CRUD
    # ------------------------------------------------------------------ #
    @app.route("/tasks")
    @login_required
    def dashboard():
        """Show the logged-in user's tasks with filtering, search and sorting."""
        status = normalize_choice(request.args.get("status", "all"), STATUSES + ("all",), default="all")
        priority = normalize_choice(request.args.get("priority", "all"), PRIORITIES + ("all",), default="all")
        search = request.args.get("q", "").strip()
        sort = normalize_choice(request.args.get("sort", "due_date"), tuple(SORTABLE_COLUMNS.keys()), default="due_date")
        order = "desc" if (request.args.get("order", "asc") or "").strip().lower() == "desc" else "asc"

        query = Task.query.filter_by(user_id=current_user_id())
        if status != "all":
            query = query.filter(Task.status == status)
        if priority != "all":
            query = query.filter(Task.priority == priority)
        if search:
            pattern = f"%{search}%"
            query = query.filter(
                db.or_(Task.title.ilike(pattern), Task.description.ilike(pattern))
            )

        column = SORTABLE_COLUMNS.get(sort, Task.due_date)
        query = query.order_by(column.desc() if order == "desc" else column.asc())
        tasks = query.all()

        # Counts for the summary cards are computed over *all* of the user's
        # tasks, not just the filtered ones.
        counts = dict(
            db.session.query(Task.status, db.func.count(Task.id))
            .filter(Task.user_id == current_user_id())
            .group_by(Task.status)
            .all()
        )
        stats = {s: counts.get(s, 0) for s in STATUSES}
        stats["total"] = sum(stats.values())

        return render_template(
            "dashboard.html",
            tasks=tasks,
            stats=stats,
            filters={"status": status, "priority": priority, "q": search,
                     "sort": sort, "order": order},
        )

    @app.route("/tasks/new", methods=["GET", "POST"])
    @login_required
    def create_task():
        """Create a task for the logged-in user."""
        if request.method == "POST":
            data, errors = validate_task(request.form)
            if errors:
                flash_errors(errors)
                return render_template("task_form.html", task=None, form=data), 400

            task = Task(
                user_id=current_user_id(),
                title=data["title"],
                description=data["description"] or None,
                due_date=data["due_date"],
                status=data["status"],
                priority=data["priority"],
            )
            try:
                db.session.add(task)
                db.session.commit()
            except SQLAlchemyError:
                db.session.rollback()
                flash("Could not save the task. Please try again.", "danger")
                return render_template("task_form.html", task=None, form=data), 500

            flash("Task created successfully.", "success")
            return redirect(url_for("dashboard"))

        return render_template("task_form.html", task=None, form={"due_date_raw": today_iso()})

    @app.route("/tasks/<int:task_id>/edit", methods=["GET", "POST"])
    @login_required
    def edit_task(task_id):
        """Edit an existing task owned by the logged-in user."""
        task = get_owned_task_or_404(task_id)

        if request.method == "POST":
            data, errors = validate_task(request.form)
            if errors:
                flash_errors(errors)
                return render_template("task_form.html", task=task, form=data), 400

            task.title = data["title"]
            task.description = data["description"] or None
            task.due_date = data["due_date"]
            task.status = data["status"]
            task.priority = data["priority"]
            try:
                db.session.commit()
            except SQLAlchemyError:
                db.session.rollback()
                flash("Could not update the task. Please try again.", "danger")
                return render_template("task_form.html", task=task, form=data), 500

            flash("Task updated successfully.", "success")
            return redirect(url_for("dashboard"))

        form = {
            "title": task.title,
            "description": task.description or "",
            "due_date_raw": task.due_date.isoformat(),
            "status": task.status,
            "priority": task.priority,
        }
        return render_template("task_form.html", task=task, form=form)

    @app.route("/tasks/<int:task_id>/delete", methods=["POST"])
    @login_required
    def delete_task(task_id):
        """Delete a task owned by the logged-in user."""
        task = get_owned_task_or_404(task_id)
        try:
            db.session.delete(task)
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            flash("Could not delete the task. Please try again.", "danger")
            return redirect(url_for("dashboard"))

        flash("Task deleted.", "info")
        return redirect(url_for("dashboard"))

    @app.route("/tasks/<int:task_id>/toggle", methods=["POST"])
    @login_required
    def toggle_task(task_id):
        """Mark a task Completed, or reopen it as To Do."""
        task = get_owned_task_or_404(task_id)
        task.status = "To Do" if task.status == "Completed" else "Completed"
        db.session.commit()
        return redirect(request.referrer or url_for("dashboard"))

    # ------------------------------------------------------------------ #
    # Advanced features: CSV export and JSON API
    # ------------------------------------------------------------------ #
    @app.route("/tasks/export")
    @login_required
    def export_tasks():
        """Download all of the user's tasks as a CSV file."""
        tasks = (
            Task.query.filter_by(user_id=current_user_id())
            .order_by(Task.due_date.asc())
            .all()
        )
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["id", "title", "description", "due_date", "status", "priority"])
        for t in tasks:
            writer.writerow([t.id, t.title, t.description or "", t.due_date.isoformat(),
                             t.status, t.priority])

        return Response(
            buffer.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment; filename=tasks.csv"},
        )

    @app.route("/api/tasks")
    @login_required
    def api_tasks():
        """Return the user's tasks as JSON (session-authenticated)."""
        tasks = Task.query.filter_by(user_id=current_user_id()).order_by(Task.due_date).all()
        return jsonify([
            {
                "id": t.id,
                "title": t.title,
                "description": t.description,
                "due_date": t.due_date.isoformat(),
                "status": t.status,
                "priority": t.priority,
            }
            for t in tasks
        ])


# Module-level app for ``python app.py`` and ``gunicorn app:app``.
app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
