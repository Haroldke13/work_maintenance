from flask import Blueprint


helpdesk_bp = Blueprint(
    "helpdesk",
    __name__,
    template_folder="templates",
    static_folder="static",
    static_url_path="/static",
)
