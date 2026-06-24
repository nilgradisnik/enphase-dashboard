import os
from datetime import datetime, date, time, timedelta, timezone
from sqlalchemy import or_
from db import db, MeterReading, DailyStats

def normalize_dt(dt):
    """Ensure datetimes are timezone-naive representing UTC for safe mathematical comparisons."""
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt

def get_gateway_readings():
    """Fetch readings from Enphase Envoy Gateway."""
    from app import load_config, get_authenticated_gateway
    config = load_config()
    gateway = get_authenticated_gateway(config)
    # Perform API call
    data = gateway.api_call('/ivp/meters/readings')
    if not data or len(data) < 2:
        raise ValueError("Invalid readings payload from Gateway")
    return data

def record_reading(app):
    """Background task to fetch readings and record them in the database."""
    with app.app_context():
        try:
            data = get_gateway_readings()
            
            # Extract Production Meter (index 0)
            prod_meter = data[0]
            prod_wh = prod_meter.get('actEnergyDlvd', 0.0)
            
            # Extract Grid Meter (index 1)
            grid_meter = data[1]
            import_wh = grid_meter.get('actEnergyDlvd', 0.0)
            export_wh = grid_meter.get('actEnergyRcvd', 0.0)
            
            # Use timestamp from gateway or fallback to current UTC time (naive UTC for SQL compatibility)
            gw_ts = prod_meter.get('timestamp')
            if gw_ts:
                timestamp = normalize_dt(datetime.fromtimestamp(gw_ts, tz=timezone.utc))
            else:
                timestamp = normalize_dt(datetime.now(timezone.utc))
            
            # Check if this reading already exists
            existing = db.session.get(MeterReading, timestamp)
            if existing:
                print(f"Reading at {timestamp} already exists. Skipping.")
                return
            
            # Get the previous reading before inserting the new one, to check for gaps
            prev_reading = MeterReading.query.order_by(MeterReading.timestamp.desc()).first()
            prev_ts = normalize_dt(prev_reading.timestamp) if prev_reading else None
            
            new_reading = MeterReading(
                timestamp=timestamp,
                production_wh=prod_wh,
                import_wh=import_wh,
                export_wh=export_wh
            )
            db.session.add(new_reading)
            db.session.commit()
            print(f"Recorded reading at {timestamp} UTC: Prod={prod_wh} Wh, Import={import_wh} Wh, Export={export_wh} Wh")
            
            # If a gap of > 2 hours is detected, handle it
            if prev_ts:
                time_diff = timestamp - prev_ts
                if time_diff > timedelta(hours=2):
                    print(f"Gap detected between {prev_ts} and {timestamp} ({time_diff.total_seconds()/3600:.2f} hours). Interpolating...")
                    interpolate_gap(prev_reading, new_reading)
                else:
                    # Normal update: recalculate today's stats
                    aggregate_day(timestamp.date())
            else:
                # First reading: aggregate today
                aggregate_day(timestamp.date())
                
        except Exception as e:
            db.session.rollback()
            print(f"Error in record_reading: {e}")

def interpolate_gap(prev_reading, new_reading):
    """
    Interpolate missing daily values when the collector was offline.
    Spreads the delta energy proportionally across the days of the gap.
    """
    t_start = normalize_dt(prev_reading.timestamp)
    t_end = normalize_dt(new_reading.timestamp)
    
    prod_delta = new_reading.production_wh - prev_reading.production_wh
    import_delta = new_reading.import_wh - prev_reading.import_wh
    export_delta = new_reading.export_wh - prev_reading.export_wh
    
    total_seconds = (t_end - t_start).total_seconds()
    if total_seconds <= 0:
        return
        
    start_date = t_start.date()
    end_date = t_end.date()
    
    # Calculate days in the interval
    current_date = start_date
    while current_date <= end_date:
        # Determine the boundaries of the gap within this calendar day (naive UTC datetimes)
        day_start_dt = datetime.combine(current_date, time.min)
        day_end_dt = datetime.combine(current_date, time.max)
        
        # Overlap of the gap with this calendar day
        overlap_start = max(t_start, day_start_dt)
        overlap_end = min(t_end, day_end_dt)
        overlap_secs = (overlap_end - overlap_start).total_seconds()
        
        if overlap_secs > 0:
            fraction = overlap_secs / total_seconds
            
            # Daily energy slices (in kWh)
            prod_kwh = max(0.0, (prod_delta * fraction) / 1000.0)
            import_kwh = max(0.0, (import_delta * fraction) / 1000.0)
            export_kwh = max(0.0, (export_delta * fraction) / 1000.0)
            cons_kwh = max(0.0, prod_kwh - export_kwh + import_kwh)
            
            # Insert or update DailyStats for this date
            stats = db.session.get(DailyStats, current_date)
            if not stats:
                stats = DailyStats(date=current_date)
                db.session.add(stats)
            
            stats.production_kwh = prod_kwh
            stats.import_kwh = import_kwh
            stats.export_kwh = export_kwh
            stats.consumption_kwh = cons_kwh
            stats.is_interpolated = True
            
            print(f"Interpolated stats for {current_date}: Prod={prod_kwh:.2f} kWh, Cons={cons_kwh:.2f} kWh (Flagged as interpolated)")
            
        current_date += timedelta(days=1)
        
    db.session.commit()

def aggregate_day(day_date):
    """
    Calculate the production and consumption metrics for a specific date.
    Finds the earliest and latest readings on that day, and computes the delta.
    """
    day_start = datetime.combine(day_date, time.min)
    day_end = datetime.combine(day_date, time.max)
    
    # 1. Find the first reading of the day
    # Look for the last reading of the PREVIOUS day to use as start-of-day reference
    start_reading = MeterReading.query.filter(
        MeterReading.timestamp < day_start
    ).order_by(MeterReading.timestamp.desc()).first()
    
    # Fallback to the first reading ON the day if no previous day record exists
    if not start_reading:
        start_reading = MeterReading.query.filter(
            MeterReading.timestamp >= day_start,
            MeterReading.timestamp <= day_end
        ).order_by(MeterReading.timestamp.asc()).first()
        
    # 2. Find the last reading of the day
    end_reading = MeterReading.query.filter(
        MeterReading.timestamp >= day_start,
        MeterReading.timestamp <= day_end
    ).order_by(MeterReading.timestamp.desc()).first()
    
    if not start_reading or not end_reading or start_reading.timestamp == end_reading.timestamp:
        # Not enough data for this day yet
        return
        
    # 3. Compute differences
    prod_diff = end_reading.production_wh - start_reading.production_wh
    import_diff = end_reading.import_wh - start_reading.import_wh
    export_diff = end_reading.export_wh - start_reading.export_wh
    
    # Bound below by 0
    prod_kwh = max(0.0, prod_diff / 1000.0)
    import_kwh = max(0.0, import_diff / 1000.0)
    export_kwh = max(0.0, export_diff / 1000.0)
    cons_kwh = max(0.0, prod_kwh - export_kwh + import_kwh)
    
    # 4. Save to DailyStats
    stats = db.session.get(DailyStats, day_date)
    if not stats:
        stats = DailyStats(date=day_date)
        db.session.add(stats)
        
    stats.production_kwh = prod_kwh
    stats.import_kwh = import_kwh
    stats.export_kwh = export_kwh
    stats.consumption_kwh = cons_kwh
    stats.is_interpolated = False
    
    db.session.commit()
    print(f"Aggregated stats for {day_date}: Prod={prod_kwh:.2f} kWh, Import={import_kwh:.2f} kWh, Export={export_kwh:.2f} kWh, Cons={cons_kwh:.2f} kWh")
