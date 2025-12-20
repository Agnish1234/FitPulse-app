import sqlite3
from datetime import datetime
import os
import logging

from models import calculate_calories

def init_db():
    conn = sqlite3.connect('fitpulse.db', detect_types=sqlite3.PARSE_DECLTYPES)
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS workouts
                 (id INTEGER PRIMARY KEY, 
                  timestamp TIMESTAMP, total_duration REAL,
                  total_calories REAL, notes TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS exercises
                 (id INTEGER PRIMARY KEY, workout_id INTEGER,
                  name TEXT, duration INTEGER, calories REAL,
                  FOREIGN KEY(workout_id) REFERENCES workouts(id) ON DELETE CASCADE)''')
    
    conn.commit()
    conn.close()
    return True

def save_workout_to_db(exercises, total_time, total_calories, notes):
    try:
        conn = sqlite3.connect('fitpulse.db', detect_types=sqlite3.PARSE_DECLTYPES)
        c = conn.cursor()
        
        # Insert workout
        c.execute(
            "INSERT INTO workouts (timestamp, total_duration, total_calories, notes) VALUES (?, ?, ?, ?)",
            (datetime.now(), float(total_time), float(total_calories), notes)
        )
        workout_id = c.lastrowid
        
        # Insert exercises
        for ex in exercises:
            calories = calculate_calories(ex['exercise'], ex['duration'])
            c.execute(
                "INSERT INTO exercises (workout_id, name, duration, calories) VALUES (?, ?, ?, ?)",
                (workout_id, ex['exercise'], ex['duration'], calories)
            )
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logging.error(f"Error saving workout: {e}")
        return False

def load_paginated_workout_history(limit=10, offset=0):
    try:
        conn = sqlite3.connect('fitpulse.db', detect_types=sqlite3.PARSE_DECLTYPES)
        c = conn.cursor()
        c.execute('''
            SELECT w.timestamp, w.total_duration, w.total_calories, w.notes,
                   GROUP_CONCAT(e.name || ' (' || e.duration || 's)') as exercises
            FROM workouts w
            LEFT JOIN exercises e ON w.id = e.workout_id
            GROUP BY w.id
            ORDER BY w.timestamp DESC
            LIMIT ? OFFSET ?
        ''', (limit, offset))
        
        result = c.fetchall()
        conn.close()
        return result
    except Exception as e:
        logging.error(f"Error loading workout history: {e}")
        return []

# NEW: Function to delete specific workout
def delete_workout(workout_id):
    try:
        conn = sqlite3.connect('fitpulse.db', detect_types=sqlite3.PARSE_DECLTYPES)
        c = conn.cursor()
        
        # Delete the workout (cascade will delete exercises)
        c.execute("DELETE FROM workouts WHERE id = ?", (workout_id,))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logging.error(f"Error deleting workout: {e}")
        return False

def load_all_workout_ids():
    """Get all workout IDs for delete functionality"""
    try:
        conn = sqlite3.connect('fitpulse.db', detect_types=sqlite3.PARSE_DECLTYPES)
        c = conn.cursor()
        c.execute("SELECT id, timestamp FROM workouts ORDER BY timestamp DESC")
        result = c.fetchall()
        conn.close()
        return result
    except Exception as e:
        logging.error(f"Error loading workout IDs: {e}")
        return []

def load_exercise_stats():
    try:
        conn = sqlite3.connect('fitpulse.db', detect_types=sqlite3.PARSE_DECLTYPES)
        c = conn.cursor()
        c.execute('''
            SELECT name, COUNT(*) as count, SUM(duration) as total_duration
            FROM exercises 
            GROUP BY name 
            ORDER BY total_duration DESC
        ''')
        
        result = c.fetchall()
        conn.close()
        return result
    except Exception as e:
        logging.error(f"Error loading exercise stats: {e}")
        return []

def load_weekly_progress():
    try:
        conn = sqlite3.connect('fitpulse.db', detect_types=sqlite3.PARSE_DECLTYPES)
        c = conn.cursor()
        c.execute('''
            SELECT 
                strftime('%Y-%m-%d', timestamp, 'weekday 0', '-6 days') as week_start,
                SUM(total_duration) as total_duration,
                SUM(total_calories) as total_calories,
                COUNT(*) as workout_count
            FROM workouts 
            GROUP BY strftime('%Y-%W', timestamp)
            ORDER BY week_start
        ''')
        
        result = c.fetchall()
        conn.close()
        return result
    except Exception as e:
        logging.error(f"Error loading weekly progress: {e}")
        return []

def clear_workout_history():
    try:
        conn = sqlite3.connect('fitpulse.db', detect_types=sqlite3.PARSE_DECLTYPES)
        c = conn.cursor()
        c.execute("DELETE FROM exercises")
        c.execute("DELETE FROM workouts")
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logging.error(f"Error clearing history: {e}")
        return False
