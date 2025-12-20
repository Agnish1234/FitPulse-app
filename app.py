import streamlit as st
from datetime import datetime
from streamlit_autorefresh import st_autorefresh
import time

from database import (
    init_db, save_workout_to_db, load_paginated_workout_history,
    load_exercise_stats, load_weekly_progress, clear_workout_history,
    delete_workout, load_all_workout_ids
)
from models import (
    MET_VALUES, WORKOUT_PROGRAMS, calculate_calories, format_time
)

# Initialize database
init_db()

# ----------------------------
# Session State Initialization
# ----------------------------
if 'workout_data' not in st.session_state:
    st.session_state.workout_data = {
        'exercises': [],
        'timer_running': False,
        'paused': False,
        'current_index': 0,
        'remaining_time': 0,
        'rest_time': 30,
        'notes': "",
        'workout_complete': False,
        'start_time': None,
        'is_rest_period': False
    }

if 'history_page' not in st.session_state:
    st.session_state.history_page = 0

if 'show_delete_confirm' not in st.session_state:
    st.session_state.show_delete_confirm = False

if 'workout_to_delete' not in st.session_state:
    st.session_state.workout_to_delete = None

if 'show_analytics_history' not in st.session_state:
    st.session_state.show_analytics_history = True  # Always show by default

if 'show_clear_all_confirm' not in st.session_state:
    st.session_state.show_clear_all_confirm = False

# Auto-refresh for timer
if st.session_state.workout_data['timer_running'] and not st.session_state.workout_data['paused']:
    st_autorefresh(interval=1000, limit=None, key="timer_refresh")

# ----------------------------
# Timer Update Function
# ----------------------------
def update_timer():
    data = st.session_state.workout_data
    
    if data['timer_running'] and not data['paused']:
        data['remaining_time'] -= 1
        
        if data['remaining_time'] <= 0:
            if data['is_rest_period']:
                data['is_rest_period'] = False
                data['current_index'] += 1
                if data['current_index'] < len(data['exercises']):
                    data['remaining_time'] = data['exercises'][data['current_index']]['duration']
                else:
                    data['timer_running'] = False
                    data['workout_complete'] = True
                    save_and_refresh()
            else:
                if data['current_index'] < len(data['exercises']) - 1:
                    data['is_rest_period'] = True
                    data['remaining_time'] = data['rest_time']
                else:
                    data['timer_running'] = False
                    data['workout_complete'] = True
                    save_and_refresh()

def save_and_refresh():
    """Save workout and refresh UI"""
    data = st.session_state.workout_data
    
    if data['exercises']:
        total_time = sum(ex['duration'] for ex in data['exercises'])
        total_calories = sum(calculate_calories(ex['exercise'], ex['duration']) for ex in data['exercises'])
        
        if save_workout_to_db(data['exercises'], total_time, total_calories, data['notes']):
            st.balloons()
    
    time.sleep(0.5)
    st.rerun()

def reset_workout():
    """Reset the current workout"""
    st.session_state.workout_data = {
        'exercises': [],
        'timer_running': False,
        'paused': False,
        'current_index': 0,
        'remaining_time': 0,
        'rest_time': st.session_state.workout_data['rest_time'],
        'notes': "",
        'workout_complete': False,
        'start_time': None,
        'is_rest_period': False
    }

# ----------------------------
# Main Application
# ----------------------------
st.set_page_config(page_title="FitPulse", page_icon="🏃", layout="wide")
st.title("🏃 FitPulse Workout Tracker")

# Update timer
if st.session_state.workout_data['timer_running']:
    update_timer()

# Main layout
col1, col2 = st.columns([1, 2])

with col1:
    st.header("➕ Add Exercise")
    
    exercise_name = st.selectbox("Exercise", list(MET_VALUES.keys()))
    
    minutes = st.number_input("Minutes", 0, 60, 0, 1)
    seconds = st.number_input("Seconds", 0, 59, 30, 10)
    exercise_duration = minutes * 60 + seconds
    
    if st.button("➕ Add Exercise", use_container_width=True):
        st.session_state.workout_data['exercises'].append({
            'exercise': exercise_name,
            'duration': exercise_duration
        })
        st.success(f"Added {exercise_name}")
        time.sleep(0.5)
        st.rerun()
    
    st.session_state.workout_data['rest_time'] = st.number_input(
        "Rest time (seconds)", 10, 300, st.session_state.workout_data['rest_time'], 10
    )
    
    st.subheader("📋 Programs")
    program = st.selectbox("Choose program", ["Custom"] + list(WORKOUT_PROGRAMS.keys()))
    if program != "Custom" and st.button("Load Program"):
        st.session_state.workout_data['exercises'] = WORKOUT_PROGRAMS[program].copy()
        time.sleep(0.5)
        st.rerun()
    
    if st.session_state.workout_data['exercises']:
        st.subheader("Current Exercises")
        total_time = 0
        total_calories = 0
        
        for i, ex in enumerate(st.session_state.workout_data['exercises']):
            calories = calculate_calories(ex['exercise'], ex['duration'])
            total_time += ex['duration']
            total_calories += calories
            
            col_ex, col_del = st.columns([4, 1])
            with col_ex:
                st.write(f"**{ex['exercise']}** - {format_time(ex['duration'])} (🔥 {calories:.1f} cal)")
            with col_del:
                if st.button("❌", key=f"del_{i}"):
                    st.session_state.workout_data['exercises'].pop(i)
                    time.sleep(0.5)
                    st.rerun()
        
        st.write(f"**Total:** {format_time(total_time)} - 🔥 {total_calories:.1f} calories")
        
        if st.button("🗑️ Clear All", use_container_width=True):
            st.session_state.workout_data['exercises'] = []
            time.sleep(0.5)
            st.rerun()
    
    if st.session_state.workout_data['exercises'] and not st.session_state.workout_data['timer_running']:
        if st.button("▶️ Start Workout", type="primary", use_container_width=True):
            st.session_state.workout_data['timer_running'] = True
            st.session_state.workout_data['current_index'] = 0
            st.session_state.workout_data['remaining_time'] = st.session_state.workout_data['exercises'][0]['duration']
            st.session_state.workout_data['start_time'] = datetime.now()
            time.sleep(0.5)
            st.rerun()
    
    st.session_state.workout_data['notes'] = st.text_area("Workout Notes", st.session_state.workout_data['notes'])

with col2:
    st.header("🏁 Workout Progress")
    
    data = st.session_state.workout_data
    
    if data['timer_running']:
        if data['is_rest_period']:
            st.subheader("🔄 REST")
            st.metric("Time Remaining", f"{data['remaining_time']}s")
            if data['current_index'] + 1 < len(data['exercises']):
                st.info(f"Next: {data['exercises'][data['current_index'] + 1]['exercise']}")
        else:
            current = data['exercises'][data['current_index']]
            st.subheader(f"{current['exercise']}")
            st.metric("Time Remaining", f"{data['remaining_time']}s")
            
            progress = 1 - (data['remaining_time'] / current['duration'])
            st.progress(min(max(progress, 0), 1))
        
        if st.button("⏸️ Pause" if not data['paused'] else "▶️ Resume"):
            data['paused'] = not data['paused']
            time.sleep(0.5)
            st.rerun()
    
    elif data['workout_complete']:
        st.balloons()
        st.success("🎉 Workout Complete!")
        if st.button("🔄 New Workout"):
            reset_workout()
            time.sleep(0.5)
            st.rerun()
    
    elif data['exercises']:
        st.info("Ready to start! Click 'Start Workout' to begin.")
    else:
        st.info("Add exercises to get started!")

# Analytics & History Section - ALWAYS VISIBLE
st.divider()
st.header("📊 Analytics & History")

# Analytics Section
st.subheader("📈 Workout Statistics")

# Load and display analytics
weekly_data = load_weekly_progress()
exercise_stats = load_exercise_stats()

if weekly_data:
    st.write("**Weekly Progress:**")
    for week in weekly_data:
        hours = int(week[1] / 3600) if week[1] else 0
        minutes = int((week[1] % 3600) / 60) if week[1] else 0
        st.write(f"• **Week {week[0]}**: {week[3]} workouts, {hours}h {minutes}m, {week[2]:.0f} calories")
else:
    st.info("No weekly data yet. Complete workouts to see progress!")

if exercise_stats:
    st.write("**Top Exercises:**")
    for exercise in exercise_stats[:5]:
        hours = int(exercise[2] / 3600) if exercise[2] else 0
        minutes = int((exercise[2] % 3600) / 60) if exercise[2] else 0
        st.write(f"• **{exercise[0]}**: {exercise[1]} times, {hours}h {minutes}m total")

# History Section with DELETE FUNCTIONALITY
st.divider()
st.subheader("📋 Workout History")

# Load history
history = load_paginated_workout_history(limit=10, offset=st.session_state.history_page * 10)

if history:
    # Stats
    total_workouts = len(history)
    total_duration = sum(row[1] for row in history if row[1])
    total_calories = sum(row[2] for row in history if row[2])
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Workouts", total_workouts)
    
    hours = int(total_duration // 3600)
    minutes = int((total_duration % 3600) // 60)
    col2.metric("Total Time", f"{hours}h {minutes}m")
    
    col3.metric("Total Calories", f"{int(total_calories)}")
    
    # Delete buttons for each workout
    st.write("**Recent Workouts (Click to expand):**")
    
    # Get all workout IDs for deletion
    workout_ids = load_all_workout_ids()
    
    for i, workout in enumerate(history):
        workout_time = format_time(int(workout[1])) if workout[1] else "00:00"
        
        with st.expander(f"{i+1}. {workout[0]} - {workout_time} - {workout[2]:.0f} kcal", expanded=False):
            if workout[4]:
                st.write(f"**Exercises:** {workout[4]}")
            if workout[3]:
                st.write(f"**Notes:** {workout[3]}")
            
            # Delete button for this specific workout
            if i < len(workout_ids):
                workout_id = workout_ids[i][0]
                if st.button(f"🗑️ Delete This Workout", key=f"delete_{workout_id}"):
                    st.session_state.workout_to_delete = workout_id
                    st.session_state.show_delete_confirm = True
                    st.rerun()
    
    # Confirmation dialog for individual deletion
    if st.session_state.show_delete_confirm and st.session_state.workout_to_delete:
        st.warning(f"⚠️ Are you sure you want to delete this workout?")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Yes, Delete", type="primary"):
                if delete_workout(st.session_state.workout_to_delete):
                    st.success("Workout deleted!")
                    st.session_state.show_delete_confirm = False
                    st.session_state.workout_to_delete = None
                    time.sleep(0.5)
                    st.rerun()
        with col2:
            if st.button("❌ Cancel"):
                st.session_state.show_delete_confirm = False
                st.session_state.workout_to_delete = None
                st.rerun()
    
    # Pagination
    st.divider()
    col1, col2, col3 = st.columns([1, 2, 1])
    with col1:
        if st.button("⬅️ Previous") and st.session_state.history_page > 0:
            st.session_state.history_page -= 1
            time.sleep(0.5)
            st.rerun()
    with col2:
        st.write(f"Page {st.session_state.history_page + 1}")
    with col3:
        if st.button("Next ➡️"):
            st.session_state.history_page += 1
            time.sleep(0.5)
            st.rerun()
    
    # Clear ALL history button - ALWAYS VISIBLE
    st.divider()
    if st.button("⚠️ CLEAR ALL HISTORY", type="secondary", use_container_width=True):
        st.session_state.show_clear_all_confirm = True
        st.rerun()

# Confirmation for clearing all history
if st.session_state.show_clear_all_confirm:
    st.warning("⚠️ ARE YOU SURE? This will delete ALL workout history permanently!")
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        if st.button("✅ YES, DELETE EVERYTHING", type="primary", use_container_width=True):
            if clear_workout_history():
                st.success("All history cleared!")
                st.session_state.history_page = 0
                st.session_state.show_clear_all_confirm = False
                time.sleep(1)
                st.rerun()
    with col3:
        if st.button("❌ Cancel", type="secondary", use_container_width=True):
            st.session_state.show_clear_all_confirm = False
            st.rerun()

# Show message only when there's no history at all (first page)
if not history and st.session_state.history_page == 0:
    st.info("No workout history yet. Complete a workout to see it here!")

# If on a page with no history but not the first page, go back
if not history and st.session_state.history_page > 0:
    st.warning("No more workouts. Going back to first page.")
    st.session_state.history_page = 0
    time.sleep(0.5)
    st.rerun()

# Footer
st.divider()
st.caption("FitPulse v2.0 | 💪 Track, Analyze, Improve!")

# Instructions
with st.expander("ℹ️ How to use this app"):
    st.write("""
    1. **Add Exercises**: Select an exercise and duration, then click 'Add Exercise'
    2. **Start Workout**: Click 'Start Workout' to begin your session
    3. **Track Progress**: Watch the timer and progress bar during your workout
    4. **View Analytics**: After completing workouts, view statistics above
    5. **Manage History**: Expand workouts to see details or delete individual workouts
    6. **Clear History**: Use the 'CLEAR ALL HISTORY' button to delete everything and start fresh
    """)
