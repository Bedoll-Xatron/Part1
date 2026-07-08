from .kr_market import kr_bp
from .chart_analysis import chart_bp
from .chart_analysis_us import chart_us_bp

def register_blueprints(app):
    app.register_blueprint(kr_bp, url_prefix='/api/kr')
    app.register_blueprint(chart_bp, url_prefix='/api/chart-analysis')
    app.register_blueprint(chart_us_bp, url_prefix='/api/us/chart-analysis')
