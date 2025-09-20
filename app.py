import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import sqlite3
import json
import os
import time
import hashlib
import uuid
from streamlit_autorefresh import st_autorefresh
import unittest
from unittest.mock import patch
import tempfile
import requests
from io import BytesIO
from PIL import Image
import logging
from typing import List, Dict, Tuple, Optional, Union
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor
import asyncio

# ----------------------------
# Configuration
# ----------------------------
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
st.set_page_config(
    page_title="FitPulse - Professional Workout Tracker",
    page_icon="🏃",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ----------------------------
# Custom CSS
# ----------------------------
st.markdown("""
<style>
    .workout-card {
        background-color: #f0f2f6;
        border-radius: 10px;
        padding: 15px;
        margin-bottom: 10px;
        border-left: 5px solid #ff4b4b;
    }
    .timer-display {
        font-size: 3rem;
        font-weight: bold;
        text-align: center;
        color: #ff4b4b;
    }
    .achievement-badge {
        background: linear-gradient(45deg, #FFD700, #FFA500);
        border-radius: 50%;
        width: 60px;
        height: 60px;
        display: flex;
        align-items: center;
        justify-content: center;
        margin: 0 auto;
        font-size: 1.5rem;
        box-shadow: 0 4px 8px rgba(0,0,0,0.2);
    }
    .program-card {
        border: 1px solid #ddd;
        border-radius: 10px;
        padding: 15px;
        margin: 10px 0;
        transition: transform 0.2s;
    }
    .program-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 10px 20px rgba(0,0,0,0.1);
    }
    @media (max-width: 768px) {
        .timer-display {
            font-size: 2rem;
        }
        .column-container {
            flex-direction: column;
        }
    }
</style>
""", unsafe_allow_html=True)

# ----------------------------
# Database Setup with Python 3.12 compatibility
# ----------------------------
def init_db() -> sqlite3.Connection:
    """Initialize SQLite database with tables and indexes"""
    conn = sqlite3.connect('fitpulse.db', detect_types=sqlite3.PARSE_DECLTYPES)
    c = conn.cursor()
    
    # Enable foreign keys
    c.execute("PRAGMA foreign_keys = ON")
    
    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY, username TEXT UNIQUE, 
                  password_hash TEXT, created_at TIMESTAMP)''')
    
    # Workouts table
    c.execute('''CREATE TABLE IF NOT EXISTS workouts
                 (id INTEGER PRIMARY KEY, user_id INTEGER, 
                  timestamp TIMESTAMP, total_duration INTEGER,
                  total_calories REAL, notes TEXT,
                  FOREIGN KEY(user_id) REFERENCES users(id))''')
    
    # Exercises table
    c.execute('''CREATE TABLE IF NOT EXISTS exercises
                 (id INTEGER PRIMARY KEY, workout_id INTEGER,
                  name TEXT, duration INTEGER, calories REAL,
                  FOREIGN KEY(workout_id) REFERENCES workouts(id) ON DELETE CASCADE)''')
    
    # Achievements table
    c.execute('''CREATE TABLE IF NOT EXISTS achievements
                 (id INTEGER PRIMARY KEY, user_id INTEGER,
                  name TEXT, description TEXT, earned_at TIMESTAMP,
                  FOREIGN KEY(user_id) REFERENCES users(id))''')
    
    # Workout templates table
    c.execute('''CREATE TABLE IF NOT EXISTS workout_templates
                 (id INTEGER PRIMARY KEY, user_id INTEGER,
                  name TEXT, description TEXT, exercises TEXT,
                  created_at TIMESTAMP, is_public BOOLEAN DEFAULT 0,
                  FOREIGN KEY(user_id) REFERENCES users(id))''')
    
    # Create indexes for performance
    c.execute("CREATE INDEX IF NOT EXISTS idx_workouts_user_id ON workouts(user_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_workouts_timestamp ON workouts(timestamp)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_exercises_workout_id ON exercises(workout_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_achievements_user_id ON achievements(user_id)")
    
    conn.commit()
    return conn

# Initialize database
db_conn = init_db()

# ----------------------------
# Database Backup Function
# ----------------------------
def backup_database() -> str:
    """Create automated database backups"""
    try:
        if not os.path.exists('backups'):
            os.makedirs('backups')
        backup_name = f"backups/fitpulse_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        
        # Ensure we're working with the latest data
        db_conn.commit()
        
        # Create backup
        with open('fitpulse.db', 'rb') as f:
            with open(backup_name, 'wb') as backup:
                backup.write(f.read())
        
        logging.info(f"Database backup created: {backup_name}")
        return backup_name
    except Exception as e:
        logging.error(f"Error creating database backup: {e}")
        return ""

# ----------------------------
# Authentication System
# ----------------------------
def hash_password(password: str) -> str:
    """Hash a password for storing"""
    salt = uuid.uuid4().hex
    return hashlib.sha256(salt.encode() + password.encode()).hexdigest() + ':' + salt

def check_password(hashed_password: str, user_password: str) -> bool:
    """Verify a stored password against one provided by user"""
    try:
        password, salt = hashed_password.split(':')
        return password == hashlib.sha256(salt.encode() + user_password.encode()).hexdigest()
    except:
        return False

def create_user(username: str, password: str) -> bool:
    """Create a new user"""
    try:
        c = db_conn.cursor()
        hashed_pw = hash_password(password)
        c.execute("INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
                 (username, hashed_pw, datetime.now()))
        db_conn.commit()
        
        # Create weekly backup on new user registration
        backup_database()
        
        return True
    except sqlite3.IntegrityError:
        return False
    except Exception as e:
        logging.error(f"Error creating user: {e}")
        return False

def authenticate_user(username: str, password: str) -> Optional[int]:
    """Authenticate a user"""
    try:
        c = db_conn.cursor()
        c.execute("SELECT id, password_hash FROM users WHERE username = ?", (username,))
        user = c.fetchone()
        if user and check_password(user[1], password):
            return user[0]  # Return user ID
        return None
    except Exception as e:
        logging.error(f"Error authenticating user: {e}")
        return None

# ----------------------------
# Session State Initialization
# ----------------------------
if 'user_id' not in st.session_state:
    st.session_state.user_id = None
if 'username' not in st.session_state:
    st.session_state.username = None
if 'workout_data' not in st.session_state:
    st.session_state.workout_data = {
        'exercises': [],
        'timer_running': False,
        'paused': False,
        'current_index': 0,
        'remaining_time': 0,
        'weight_kg': 70.0,
        'rest_time': 60,
        'notes': "",
        'workout_complete': False,
        'start_time': None,
        'total_workout_time': 0,
        'is_rest_period': False
    }
if 'selected_program' not in st.session_state:
    st.session_state.selected_program = None
if 'show_timer_section' not in st.session_state:
    st.session_state.show_timer_section = False
if 'confirm_clear' not in st.session_state:
    st.session_state.confirm_clear = False
if 'history_page' not in st.session_state:
    st.session_state.history_page = 0
if 'backup_status' not in st.session_state:
    st.session_state.backup_status = ""

# ----------------------------
# Auto-refresh for timer
# ----------------------------
if st.session_state.workout_data['timer_running'] and not st.session_state.workout_data['paused']:
    st_autorefresh(interval=1000, limit=None, key="timer_refresh")

# ----------------------------
# Helper Functions with Type Hints
# ----------------------------
MET_VALUES = {
    "Running": 9.8, "Cycling": 7.5, "Jumping Jacks": 8.0, "Burpees": 8.8,
    "Push-ups": 8.0, "Squats": 5.0, "Lunges": 5.0, "Plank": 3.3,
    "Yoga": 2.5, "Stretching": 2.8, "Weightlifting": 6.0, "Swimming": 7.0,
    "Walking": 4.0, "Rowing": 7.0, "HIIT": 9.0, "Pilates": 3.5
}

WORKOUT_PROGRAMS = {
    "Beginner Full Body": [
        {"exercise": "Push-ups", "duration": 180},
        {"exercise": "Squats", "duration": 240},
        {"exercise": "Plank", "duration": 120},
        {"exercise": "Lunges", "duration": 180}
    ],
    "HIIT Routine": [
        {"exercise": "Burpees", "duration": 45},
        {"exercise": "Jumping Jacks", "duration": 45},
        {"exercise": "Mountain Climbers", "duration": 45},
        {"exercise": "High Knees", "duration": 45}
    ],
    "Yoga & Stretching": [
        {"exercise": "Yoga", "duration": 600},
        {"exercise": "Stretching", "duration": 300}
    ],
    "Cardio Blast": [
        {"exercise": "Running", "duration": 1200},
        {"exercise": "Jumping Jacks", "duration": 300},
        {"exercise": "Cycling", "duration": 600}
    ]
}

ACHIEVEMENTS = {
    "first_workout": {"name": "First Steps", "description": "Complete your first workout", "icon": "🚶"},
    "marathon": {"name": "Marathoner", "description": "Complete 60+ minutes of exercise", "icon": "🏃"},
    "consistent": {"name": "Consistent", "description": "Work out 3 days in a row", "icon": "📅"},
    "variety": {"name": "Variety", "description": "Try 5 different exercises", "icon": "🌟"}
}

@lru_cache(maxsize=128)
def calculate_calories(exercise: str, seconds: int, weight: float) -> float:
    """
    Calculate calories burned for an exercise.
    
    Args:
        exercise: Name of the exercise
        seconds: Duration in seconds
        weight: User weight in kg
        
    Returns:
        Estimated calories burned
    """
    met = MET_VALUES.get(exercise, 5.0)
    return round(met * 3.5 * weight / 200 * (seconds / 60), 2)

def format_time(seconds: int) -> str:
    """Format seconds into HH:MM:SS format"""
    return str(timedelta(seconds=seconds)).split(".")[0]

def save_workout() -> bool:
    """Save workout to database with comprehensive error handling"""
    try:
        if not st.session_state.workout_data['exercises']:
            st.warning("No exercises to save!")
            return False
            
        # Calculate total workout time
        end_time = datetime.now()
        start_time = st.session_state.workout_data['start_time'] or end_time
        total_time = (end_time - start_time).total_seconds()
        
        # Save to database
        c = db_conn.cursor()
        
        # Insert workout
        c.execute(
            "INSERT INTO workouts (user_id, timestamp, total_duration, total_calories, notes) VALUES (?, ?, ?, ?, ?)",
            (st.session_state.user_id, datetime.now(), total_time, 
             sum(calculate_calories(ex['exercise'], ex['duration'], st.session_state.workout_data['weight_kg']) 
                 for ex in st.session_state.workout_data['exercises']),
             st.session_state.workout_data['notes'])
        )
        workout_id = c.lastrowid
        
        # Insert exercises
        for ex in st.session_state.workout_data['exercises']:
            calories = calculate_calories(ex['exercise'], ex['duration'], st.session_state.workout_data['weight_kg'])
            c.execute(
                "INSERT INTO exercises (workout_id, name, duration, calories) VALUES (?, ?, ?, ?)",
                (workout_id, ex['exercise'], ex['duration'], calories)
            )
        
        db_conn.commit()
        
        # Create backup after saving workout
        backup_database()
        
        # Check for achievements
        check_achievements()
        
        st.success("✅ Workout saved successfully! 🎉")
        return True
    except sqlite3.Error as e:
        logging.error(f"Database error saving workout: {e}")
        st.error("Database error occurred. Please try again.")
        return False
    except Exception as e:
        logging.error(f"Unexpected error saving workout: {e}")
        st.error("An unexpected error occurred.")
        return False

def reset_workout() -> None:
    """Reset the current workout"""
    st.session_state.workout_data = {
        'exercises': [],
        'timer_running': False,
        'paused': False,
        'current_index': 0,
        'remaining_time': 0,
        'weight_kg': st.session_state.workout_data.get('weight_kg', 70.0),
        'rest_time': max(st.session_state.workout_data.get('rest_time', 60), 1),
        'notes': "",
        'workout_complete': False,
        'start_time': None,
        'total_workout_time': 0,
        'is_rest_period': False
    }
    st.session_state.selected_program = None
    st.session_state.show_timer_section = False
    st.success("🔄 Workout reset successfully!")

def clear_workout_history() -> None:
    """Clear all workout history for the current user"""
    try:
        c = db_conn.cursor()
        
        # First get all workout IDs for this user
        c.execute("SELECT id FROM workouts WHERE user_id = ?", (st.session_state.user_id,))
        workout_ids = [row[0] for row in c.fetchall()]
        
        if workout_ids:
            # Delete exercises
            placeholders = ','.join('?' for _ in workout_ids)
            c.execute(f"DELETE FROM exercises WHERE workout_id IN ({placeholders})", workout_ids)
            
            # Delete workouts
            c.execute(f"DELETE FROM workouts WHERE id IN ({placeholders})", workout_ids)
        
        # Delete achievements
        c.execute("DELETE FROM achievements WHERE user_id = ?", (st.session_state.user_id,))
        
        db_conn.commit()
        
        # Create backup after clearing history
        backup_database()
        
        st.session_state.confirm_clear = False
        st.success("🗑️ Workout history cleared successfully!")
        st.rerun()
    except Exception as e:
        logging.error(f"Error clearing history: {e}")
        st.error(f"Error clearing history: {e}")

def load_paginated_workout_history(limit: int = 5, offset: int = 0) -> List[Tuple]:
    """Load paginated workout history for the current user"""
    try:
        c = db_conn.cursor()
        c.execute('''
            SELECT w.timestamp, w.total_duration, w.total_calories, w.notes,
                   GROUP_CONCAT(e.name || ' (' || e.duration || 's)') as exercises
            FROM workouts w
            JOIN exercises e ON w.id = e.workout_id
            WHERE w.user_id = ?
            GROUP BY w.id
            ORDER BY w.timestamp DESC
            LIMIT ? OFFSET ?
        ''', (st.session_state.user_id, limit, offset))
        
        return c.fetchall()
    except Exception as e:
        logging.error(f"Error loading workout history: {e}")
        return []

def check_achievements() -> None:
    """Check and award achievements"""
    try:
        c = db_conn.cursor()
        
        # Check first workout
        c.execute("SELECT COUNT(*) FROM workouts WHERE user_id = ?", (st.session_state.user_id,))
        workout_count = c.fetchone()[0]
        
        if workout_count == 1:
            award_achievement("first_workout")
        
        # Check for marathon (60+ minutes)
        c.execute("SELECT SUM(total_duration) FROM workouts WHERE user_id = ?", (st.session_state.user_id,))
        total_duration = c.fetchone()[0] or 0
        
        if total_duration >= 3600:  # 60 minutes
            award_achievement("marathon")
        
        # Check for variety (5 different exercises)
        c.execute("SELECT COUNT(DISTINCT name) FROM exercises WHERE workout_id IN (SELECT id FROM workouts WHERE user_id = ?)", 
                  (st.session_state.user_id,))
        exercise_variety = c.fetchone()[0]
        
        if exercise_variety >= 5:
            award_achievement("variety")
        
        # Check for consistency (3 days in a row)
        c.execute("SELECT DISTINCT DATE(timestamp) FROM workouts WHERE user_id = ? ORDER BY timestamp DESC LIMIT 3", 
                  (st.session_state.user_id,))
        recent_dates = [datetime.strptime(row[0], '%Y-%m-%d').date() for row in c.fetchall()]
        
        if len(recent_dates) >= 3:
            if (recent_dates[0] - recent_dates[2]).days == 2:
                award_achievement("consistent")
    except Exception as e:
        logging.error(f"Error checking achievements: {e}")

def award_achievement(achievement_key: str) -> None:
    """Award an achievement to the current user"""
    try:
        c = db_conn.cursor()
        
        # Check if already awarded
        c.execute("SELECT id FROM achievements WHERE user_id = ? AND name = ?", 
                  (st.session_state.user_id, ACHIEVEMENTS[achievement_key]["name"]))
        if c.fetchone() is None:
            # Award achievement
            c.execute("INSERT INTO achievements (user_id, name, description, earned_at) VALUES (?, ?, ?, ?)",
                     (st.session_state.user_id, ACHIEVEMENTS[achievement_key]["name"], 
                      ACHIEVEMENTS[achievement_key]["description"], datetime.now()))
            db_conn.commit()
            
            # Create backup after awarding achievement
            backup_database()
            
            # Show celebration
            st.balloons()
            st.success(f"🎉 Achievement Unlocked: {ACHIEVEMENTS[achievement_key]['name']}!")
    except Exception as e:
        logging.error(f"Error awarding achievement: {e}")

def load_achievements() -> List[Tuple]:
    """Load achievements for the current user"""
    try:
        c = db_conn.cursor()
        c.execute("SELECT name, description, earned_at FROM achievements WHERE user_id = ? ORDER BY earned_at DESC", 
                  (st.session_state.user_id,))
        return c.fetchall()
    except Exception as e:
        logging.error(f"Error loading achievements: {e}")
        return []

def save_workout_template(name: str, description: str = "") -> bool:
    """Save current workout as a template"""
    try:
        c = db_conn.cursor()
        exercises_json = json.dumps(st.session_state.workout_data['exercises'])
        
        c.execute(
            "INSERT INTO workout_templates (user_id, name, description, exercises, created_at) VALUES (?, ?, ?, ?, ?)",
            (st.session_state.user_id, name, description, exercises_json, datetime.now())
        )
        
        db_conn.commit()
        return True
    except Exception as e:
        logging.error(f"Error saving workout template: {e}")
        return False

def load_workout_templates() -> List[Tuple]:
    """Load workout templates for the current user"""
    try:
        c = db_conn.cursor()
        c.execute("SELECT id, name, description, exercises FROM workout_templates WHERE user_id = ? OR is_public = 1 ORDER BY created_at DESC", 
                  (st.session_state.user_id,))
        return c.fetchall()
    except Exception as e:
        logging.error(f"Error loading workout templates: {e}")
        return []

def create_advanced_analytics() -> Tuple[List[Tuple], List[Tuple]]:
    """Advanced analytics with trend analysis"""
    try:
        c = db_conn.cursor()
        
        # Weekly progress
        c.execute('''
            SELECT DATE(timestamp, 'weekday 0', '-6 days') as week_start,
                   SUM(total_duration) as total_duration,
                   SUM(total_calories) as total_calories,
                   COUNT(*) as workout_count
            FROM workouts 
            WHERE user_id = ?
            GROUP BY week_start
            ORDER BY week_start
        ''', (st.session_state.user_id,))
        
        weekly_data = c.fetchall()
        
        # Exercise frequency analysis
        c.execute('''
            SELECT name, COUNT(*) as count, SUM(duration) as total_duration
            FROM exercises 
            WHERE workout_id IN (SELECT id FROM workouts WHERE user_id = ?)
            GROUP BY name 
            ORDER BY total_duration DESC
        ''', (st.session_state.user_id,))
        
        exercise_stats = c.fetchall()
        
        return weekly_data, exercise_stats
    except Exception as e:
        logging.error(f"Error creating advanced analytics: {e}")
        return [], []

# ----------------------------
# Timer Update Function
# ----------------------------
def update_timer() -> None:
    """Update the timer countdown"""
    data = st.session_state.workout_data
    
    if data['timer_running'] and not data['paused']:
        data['remaining_time'] -= 1
        
        # Check if current exercise is complete
        if data['remaining_time'] <= 0:
            if data['is_rest_period']:
                # Rest period finished, move to next exercise
                data['is_rest_period'] = False
                data['current_index'] += 1
                if data['current_index'] < len(data['exercises']):
                    # Start next exercise
                    data['remaining_time'] = data['exercises'][data['current_index']]['duration']
                else:
                    # Workout complete
                    data['timer_running'] = False
                    data['workout_complete'] = True
                    save_workout()
            else:
                # Exercise finished, start rest period if there are more exercises
                if data['current_index'] < len(data['exercises']) - 1:
                    data['is_rest_period'] = True
                    data['remaining_time'] = data['rest_time']
                else:
                    # Last exercise finished, workout complete
                    data['timer_running'] = False
                    data['workout_complete'] = True
                    save_workout()

# ----------------------------
# Authentication UI
# ----------------------------
def show_login_register() -> None:
    """Show login/register form"""
    st.title("🏃 FitPulse - Professional Workout Tracker")
    st.markdown("### Track your workouts, measure progress, and achieve your fitness goals")
    
    tab1, tab2 = st.tabs(["Login", "Register"])
    
    with tab1:
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login")
            
            if submitted:
                user_id = authenticate_user(username, password)
                if user_id:
                    st.session_state.user_id = user_id
                    st.session_state.username = username
                    st.rerun()
                else:
                    st.error("Invalid username or password")
    
    with tab2:
        with st.form("register_form"):
            new_username = st.text_input("Choose a username")
            new_password = st.text_input("Choose a password", type="password")
            confirm_password = st.text_input("Confirm password", type="password")
            submitted = st.form_submit_button("Create Account")
            
            if submitted:
                if new_password != confirm_password:
                    st.error("Passwords don't match")
                elif len(new_password) < 6:
                    st.error("Password must be at least 6 characters")
                else:
                    if create_user(new_username, new_password):
                        st.success("Account created successfully! Please login.")
                    else:
                        st.error("Username already exists")

# ----------------------------
# Main Application UI
# ----------------------------
def show_main_app() -> None:
    """Show the main application"""
    # Header with logout button
    col1, col2, col3 = st.columns([5, 1, 1])
    with col1:
        st.title("🏃 FitPulse - Professional Workout Tracker")
    with col2:
        if st.button("Backup DB", help="Create a database backup"):
            backup_path = backup_database()
            if backup_path:
                st.session_state.backup_status = f"Backup created: {backup_path}"
            else:
                st.session_state.backup_status = "Backup failed"
    with col3:
        if st.button("Logout"):
            st.session_state.user_id = None
            st.session_state.username = None
            st.session_state.show_timer_section = False
            st.session_state.confirm_clear = False
            st.rerun()
    
    if st.session_state.backup_status:
        st.info(st.session_state.backup_status)
    
    st.divider()
    
    # Update timer on each refresh
    if st.session_state.workout_data['timer_running'] and not st.session_state.workout_data['paused']:
        update_timer()
    
    # Main layout
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.header("➕ Add Exercise")
        
        with st.expander("⚙️ Settings", expanded=True):
            st.session_state.workout_data['weight_kg'] = st.number_input(
                "Your Weight (kg)", 40.0, 150.0, st.session_state.workout_data['weight_kg'], 1.0
            )
            st.session_state.workout_data['rest_time'] = st.number_input(
                "Rest between exercises (seconds)", 1, 300, max(st.session_state.workout_data['rest_time'], 1), 10
            )
        
        # Exercise selection with common exercises
        exercise_options = list(MET_VALUES.keys())
        exercise_name = st.selectbox("Exercise Name", exercise_options, index=0)
        
        # Duration input with minutes and seconds
        col_min, col_sec = st.columns(2)
        with col_min:
            minutes = st.number_input("Minutes", 0, 60, 1, 1)
        with col_sec:
            seconds = st.number_input("Seconds", 0, 59, 0, 10)
        
        exercise_duration = minutes * 60 + seconds
        
        if st.button("➕ Add Exercise", key="add_exercise", use_container_width=True):
            st.session_state.workout_data['exercises'].append({
                'exercise': exercise_name,
                'duration': exercise_duration
            })
            st.success(f"✅ Added {exercise_name} for {format_time(exercise_duration)}")
        
        # Workout Programs
        st.subheader("📋 Workout Programs")
        program_options = list(WORKOUT_PROGRAMS.keys())
        selected_program = st.selectbox("Choose a program", ["Custom"] + program_options)
        
        # Add a button to load the selected program
        if selected_program != "Custom":
            if st.button("🔄 Load This Program", key="load_program", use_container_width=True):
                st.session_state.workout_data['exercises'] = WORKOUT_PROGRAMS[selected_program].copy()
                st.session_state.selected_program = selected_program
                st.success(f"✅ Loaded {selected_program} program!")
                st.rerun()
            
            # Show preview of the selected program
            if selected_program in WORKOUT_PROGRAMS:
                st.write("**Program Includes:**")
                for idx, ex in enumerate(WORKOUT_PROGRAMS[selected_program]):
                    calories = calculate_calories(ex['exercise'], ex['duration'], st.session_state.workout_data['weight_kg'])
                    st.markdown(f"""
                    <div class="workout-card">
                        <b>{idx+1}. {ex['exercise']}</b><br>
                        Duration: {format_time(ex['duration'])}<br>
                        Calories: 🔥 {calories} cal
                    </div>
                    """, unsafe_allow_html=True)
        
        # Workout Templates
        st.subheader("💾 Workout Templates")
        templates = load_workout_templates()
        
        if templates:
            template_names = [f"{t[1]} ({'Public' if len(t) > 4 and t[4] else 'Private'})" for t in templates]
            selected_template = st.selectbox("Your Templates", ["Select a template"] + template_names)
            
            if selected_template != "Select a template":
                template_index = template_names.index(selected_template)
                template = templates[template_index]
                
                if st.button("Load Template", key="load_template"):
                    try:
                        exercises = json.loads(template[3])
                        st.session_state.workout_data['exercises'] = exercises
                        st.session_state.selected_program = f"Template: {template[1]}"
                        st.success(f"✅ Loaded {template[1]} template!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error loading template: {e}")
        
        # Save current workout as template
        if st.session_state.workout_data['exercises']:
            with st.form("save_template_form"):
                template_name = st.text_input("Template Name")
                template_desc = st.text_area("Description (optional)")
                if st.form_submit_button("💾 Save as Template"):
                    if template_name:
                        if save_workout_template(template_name, template_desc):
                            st.success("Template saved successfully!")
                        else:
                            st.error("Error saving template")
                    else:
                        st.error("Please enter a template name")
        
        # Show current program status
        if st.session_state.selected_program:
            st.info(f"📋 Current Program: **{st.session_state.selected_program}**")
            if st.button("🚫 Clear Program", key="clear_program"):
                st.session_state.selected_program = None
                st.session_state.workout_data['exercises'] = []
                st.success("Program cleared!")
                st.rerun()

        # Display current exercises
        if st.session_state.workout_data['exercises']:
            st.subheader("Current Exercises")
            for i, ex in enumerate(st.session_state.workout_data['exercises']):
                calories = calculate_calories(ex['exercise'], ex['duration'], st.session_state.workout_data['weight_kg'])
                col_ex, col_del = st.columns([4, 1])
                with col_ex:
                    st.markdown(f"""
                    <div class="workout-card">
                        <b>{ex['exercise']}</b> - {format_time(ex['duration'])} (🔥 {calories} cal)
                    </div>
                    """, unsafe_allow_html=True)
                with col_del:
                    if st.button("❌", key=f"del_{i}"):
                        st.session_state.workout_data['exercises'].pop(i)
                        st.rerun()
            
            # Calculate totals
            total_duration = sum(ex['duration'] for ex in st.session_state.workout_data['exercises'])
            total_calories = sum(calculate_calories(ex['exercise'], ex['duration'], st.session_state.workout_data['weight_kg']) 
                                for ex in st.session_state.workout_data['exercises'])
            
            st.markdown(f"**Total:** {format_time(total_duration)} - 🔥 {total_calories:.2f} calories")
            
            # Clear exercises button
            if st.button("🗑️ Clear All Exercises", use_container_width=True):
                st.session_state.workout_data['exercises'] = []
                st.session_state.selected_program = None
                st.rerun()
            
            # Start workout button
            if not st.session_state.workout_data['timer_running']:
                if st.button("▶️ Start Workout", type="primary", use_container_width=True):
                    st.session_state.workout_data['timer_running'] = True
                    st.session_state.workout_data['current_index'] = 0
                    st.session_state.workout_data['remaining_time'] = st.session_state.workout_data['exercises'][0]['duration']
                    st.session_state.workout_data['start_time'] = datetime.now()
                    st.session_state.show_timer_section = True
                    st.rerun()
        else:
            st.info("No exercises added yet. Add some exercises or select a program to get started!")
        
        st.subheader("📝 Notes")
        st.session_state.workout_data['notes'] = st.text_area(
            "How did you feel?",
            st.session_state.workout_data['notes'],
            placeholder="Great workout! Felt strong today...",
            height=100
        )
        
        st.subheader("🎛 Controls")
        c1, c2, c3 = st.columns(3)
        
        # Start Button
        start_disabled = (not st.session_state.workout_data['exercises'] or 
                         st.session_state.workout_data['timer_running'] or
                         st.session_state.workout_data['workout_complete'])
        
        if c1.button("▶️ Start Workout", disabled=start_disabled, use_container_width=True):
            st.session_state.workout_data['timer_running'] = True
            st.session_state.workout_data['paused'] = False
            st.session_state.workout_data['current_index'] = 0
            st.session_state.workout_data['remaining_time'] = st.session_state.workout_data['exercises'][0]['duration']
            st.session_state.workout_data['workout_complete'] = False
            st.session_state.workout_data['start_time'] = datetime.now()
            st.session_state.workout_data['is_rest_period'] = False
            st.session_state.show_timer_section = True
            st.rerun()
        
        # Pause/Resume Button
        pause_text = "⏸️ Pause" if not st.session_state.workout_data['paused'] else "▶️ Resume"
        if c2.button(pause_text, disabled=not st.session_state.workout_data['timer_running'], use_container_width=True):
            st.session_state.workout_data['paused'] = not st.session_state.workout_data['paused']
            st.rerun()
        
        # Reset Button
        if c3.button("🔄 Reset", use_container_width=True):
            reset_workout()
            st.rerun()
    
    with col2:
        # Auto-scroll to timer section when workout starts
        if st.session_state.show_timer_section:
            st.markdown("<div id='timer-section'></div>", unsafe_allow_html=True)
            st.write(
                f"""
                <script>
                    window.addEventListener('load', function() {{
                        const element = document.getElementById('timer-section');
                        if (element) {{
                            element.scrollIntoView({{
                                behavior: 'smooth',
                                block: 'start'
                            }});
                        }}
                    }});
                </script>
                """,
                unsafe_allow_html=True
            )
        
        st.header("🏁 Workout Progress")
        st.divider()
        
        data = st.session_state.workout_data
        exercises = data['exercises']
        
        if data['timer_running']:
            idx = data['current_index']
            
            if data['is_rest_period'] and idx < len(exercises) - 1:
                # Rest period
                st.markdown('<div class="timer-display">REST</div>', unsafe_allow_html=True)
                st.metric("Time Remaining", f"{data['remaining_time']}s")
                
                # Progress bar for rest period
                rest_time = max(data['rest_time'], 1)
                progress = 1 - (data['remaining_time'] / rest_time)
                st.progress(min(max(progress, 0), 1))
                
                st.info(f"Rest before next exercise: {exercises[idx + 1]['exercise']}")
                
            elif idx < len(exercises):
                current = exercises[idx]
                
                # Display current exercise with timer
                st.markdown(f'<div class="timer-display">{data["remaining_time"]}s</div>', unsafe_allow_html=True)
                
                col1, col2 = st.columns([2, 1])
                with col1:
                    st.metric(
                        f"Exercise {idx+1}/{len(exercises)}", 
                        current['exercise']
                    )
                with col2:
                    status = "⏸️ Paused" if data['paused'] else "▶️ Running"
                    st.metric("Status", status)
                
                # Progress bar
                duration = max(current['duration'], 1)
                progress = 1 - (data['remaining_time'] / duration)
                st.progress(min(max(progress, 0), 1))
                
                # Calories estimation
                calories = calculate_calories(current['exercise'], current['duration'], data['weight_kg'])
                st.caption(f"🔥 Estimated calories: {calories}")
            
            else:
                data['timer_running'] = False
                data['workout_complete'] = True
                st.session_state.show_timer_section = False
                st.balloons()
                st.success("🎉 Workout complete!")
                save_workout()
        
        elif data['workout_complete']:
            st.balloons()
            st.success("🎉 Workout complete!")
            if st.button("🔄 Start New Workout"):
                reset_workout()
                st.rerun()
        
        elif exercises:
            st.info("Click ▶️ Start Workout to begin your session!")
            
            # Show workout summary before starting
            total_time = sum(ex['duration'] for ex in exercises)
            total_calories = sum(calculate_calories(ex['exercise'], ex['duration'], st.session_state.workout_data['weight_kg']) for ex in exercises)
            
            st.subheader("📋 Workout Summary")
            st.write(f"**Total Exercises:** {len(exercises)}")
            st.write(f"**Total Time:** {format_time(total_time)}")
            st.write(f"**Estimated Calories:** {total_calories:.0f} kcal")
            
        else:
            st.info("Add some exercises to get started! 🏃‍♂️")
    
    # Advanced Analytics Section
    st.divider()
    st.subheader("📊 Advanced Analytics")
    
    # Load analytics data
    weekly_data, exercise_stats = create_advanced_analytics()
    
    if weekly_data:
        # Convert to DataFrame for visualization
        weekly_df = pd.DataFrame(weekly_data, columns=['Week', 'Duration', 'Calories', 'Workouts'])
        weekly_df['Week'] = pd.to_datetime(weekly_df['Week'])
        
        # Create weekly progress chart
        fig = px.line(weekly_df, x='Week', y='Duration', title='Weekly Workout Duration Trend')
        st.plotly_chart(fig, use_container_width=True)
        
        # Exercise statistics
        if exercise_stats:
            exercise_df = pd.DataFrame(exercise_stats, columns=['Exercise', 'Count', 'Total Duration'])
            
            col1, col2 = st.columns(2)
            with col1:
                fig = px.bar(exercise_df.head(10), x='Exercise', y='Count', title='Top Exercises by Frequency')
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                fig = px.pie(exercise_df, values='Total Duration', names='Exercise', title='Exercise Time Distribution')
                st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Complete more workouts to see advanced analytics!")
    
    # Workout History Section with Pagination
    st.divider()
    st.subheader("📈 Workout History")
    
    # Pagination controls
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        st.write(f"Page {st.session_state.history_page + 1}")
    with col2:
        if st.button("⬅️ Previous", disabled=st.session_state.history_page == 0):
            st.session_state.history_page -= 1
            st.rerun()
    with col3:
        if st.button("Next ➡️"):
            st.session_state.history_page += 1
            st.rerun()
    
    # Load paginated history
    history = load_paginated_workout_history(limit=5, offset=st.session_state.history_page * 5)
    
    if history:
        # Show basic stats
        total_workouts = len(history)
        total_duration = sum(row[1] for row in history)
        total_calories = sum(row[2] for row in history)
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Workouts", total_workouts)
        col2.metric("Total Time", format_time(total_duration))
        col3.metric("Total Calories", f"{total_calories:.0f} kcal")
        
        # Clear History Button
        with col4:
            if st.button("🗑️ Clear History", use_container_width=True):
                st.session_state.confirm_clear = True
        
        # Confirmation for clearing history
        if st.session_state.confirm_clear:
            st.warning("⚠️ Are you sure you want to delete ALL your workout history? This action cannot be undone!")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ Yes, Delete Everything", type="primary", use_container_width=True):
                    clear_workout_history()
            with col2:
                if st.button("❌ Cancel", use_container_width=True):
                    st.session_state.confirm_clear = False
                    st.rerun()
        
        # Show recent workouts
        st.write("**Recent Workouts:**")
        for workout in history:
            with st.expander(f"{workout[0]} - {format_time(workout[1])} - {workout[2]:.0f} kcal"):
                st.write(f"**Exercises:** {workout[4]}")
                if workout[3]:
                    st.write(f"**Notes:** {workout[3]}")
    else:
        st.info("No workout history yet. Complete a workout to see your progress here!")
    
    # Achievements Section
    st.divider()
    st.subheader("🏆 Achievements")
    
    achievements = load_achievements()
    if achievements:
        cols = st.columns(4)
        for idx, achievement in enumerate(achievements):
            with cols[idx % 4]:
                # Find the achievement icon
                icon = "🏆"
                for key, value in ACHIEVEMENTS.items():
                    if value["name"] == achievement[0]:
                        icon = value["icon"]
                        break
                
                st.markdown(f'<div class="achievement-badge">{icon}</div>', unsafe_allow_html=True)
                st.write(f"**{achievement[0]}**")
                st.caption(achievement[1])
                st.caption(f"Earned: {achievement[2]}")
    else:
        st.info("Complete workouts to earn achievements!")
    
    # Footer
    st.divider()
    st.caption(f"💪 FitPulse - Logged in as {st.session_state.username} | Keep pushing your limits! 🚀")

# ----------------------------
# Unit Tests
# ----------------------------
def run_tests() -> None:
    """Run unit tests for the application"""
    test_dir = tempfile.mkdtemp()
    os.chdir(test_dir)
    
    # Create a test database
    test_conn = sqlite3.connect(':memory:')
    test_c = test_conn.cursor()
    
    # Create tables
    test_c.execute('''CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, password_hash TEXT)''')
    test_c.execute('''CREATE TABLE workouts (id INTEGER PRIMARY KEY, user_id INTEGER, timestamp TIMESTAMP)''')
    test_c.execute('''CREATE TABLE exercises (id INTEGER PRIMARY KEY, workout_id INTEGER, name TEXT, duration INTEGER)''')
    
    # Test password hashing
    hashed = hash_password('testpassword')
    assert check_password(hashed, 'testpassword')
    assert not check_password(hashed, 'wrongpassword')
    
    # Test calorie calculation
    assert calculate_calories("Running", 600, 70) > 0
    
    # Test time formatting
    assert format_time(3665) == "1:01:05"
    
    print("All tests passed!")

# ----------------------------
# Main Application Flow
# ----------------------------
if __name__ == "__main__":
    # Check if we're in test mode
    if "TEST_MODE" in os.environ:
        run_tests()
    else:
        # Show appropriate UI based on authentication status
        if st.session_state.user_id is None:
            show_login_register()
        else:
            show_main_app()
