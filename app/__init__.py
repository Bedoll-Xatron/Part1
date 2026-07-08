from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

from app.routes import register_blueprints
from app.routes.chart_analysis import start_scheduler


def create_app():
    app = Flask(__name__)

    CORS(app, resources={r"/api/*": {"origins": "*"}})

    register_blueprints(app)
    start_scheduler()

    # 장중 원석 스캐너 자동 스케줄러 (서버가 켜져 있으면 장중 5분마다 자동 실행)
    from app.utils.gem_scheduler import start_gem_scheduler
    start_gem_scheduler()

    return app

