from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class MeterReading(db.Model):
    __tablename__ = 'meter_readings'
    timestamp = db.Column(db.DateTime, primary_key=True, index=True)
    production_wh = db.Column(db.Float, nullable=False)
    import_wh = db.Column(db.Float, nullable=False)
    export_wh = db.Column(db.Float, nullable=False)

    def to_dict(self):
        return {
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'production_wh': self.production_wh,
            'import_wh': self.import_wh,
            'export_wh': self.export_wh
        }

class DailyStats(db.Model):
    __tablename__ = 'daily_stats'
    date = db.Column(db.Date, primary_key=True)
    production_kwh = db.Column(db.Float, nullable=False)
    import_kwh = db.Column(db.Float, nullable=False)
    export_kwh = db.Column(db.Float, nullable=False)
    consumption_kwh = db.Column(db.Float, nullable=False)
    is_interpolated = db.Column(db.Boolean, default=False, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'date': self.date.isoformat() if self.date else None,
            'production_kwh': round(self.production_kwh, 2),
            'import_kwh': round(self.import_kwh, 2),
            'export_kwh': round(self.export_kwh, 2),
            'consumption_kwh': round(self.consumption_kwh, 2),
            'is_interpolated': self.is_interpolated,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
