import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
import os
import time
from typing import List, Dict, Any

# ----------------------------
# Constants
# ----------------------------
MAX_TIME_SECONDS = 3600
DEFAULT_WEIGHT_KG = 70.0
FILENAME = "workouts.csv"
REQUIRED_COLUMNS = [
    "session_id", "exercise", "time_seconds", "date", "time",
    "category", "calories", "note", "weight_kg"
]

MET_TABLE = {
    "Running": 9.8, "Cycling": 7.5, "Jumping Jacks": 8.0, "Burpees": 8.8,
    "Mountain Climbers": 8.0, "Skipping": 12.3, "Rowing": 7.0,
    "Push-ups": 8.0, "Squats": 5.0, "Lunges": 5.0, "Plank": 3.3,
    "Yoga Stretch": 2.5, "Side Bends": 2.8
}
DEFAULT_MET_BY_CATEGORY = {"Cardio": 6.0, "Strength": 3.5, "Flexibility": 2.5, "Other": 3.0}

# ----------------------------
# Session State Initialization
# ----------------------------
if 'session' not in st.session_state:
    st.session_state.session = []
if 'timer_running' not in st.session_state:
    st.session_state.timer_running = False
if 'paused' not in st.session_state:
    st.session_state.paused = False
if 'current_index' not in st.session_state:
    st.session_state.current_index = 0
if 'remaining_time' not in st.session_state:
    st.session_state.remaining_time = 0
if 'in_rest' not in st.session_state:
    st.session_state.in_rest = False
if 'rest_remaining' not in st.session_state:
    st.session_state.rest_remaining = 0
if 'workout_complete' not in st.session_state:
    st.session_state.workout_complete = False
if 'show_chart' not in st.session_state:
    st.session_state.show_chart = False
if 'note' not in st.session_state:
    st.session_state.note = ""
if 'weight_kg' not in st.session_state:
    st.session_state.weight_kg = DEFAULT_WEIGHT_KG
if 'rest_between_ex' not in st.session_state:
    st.session_state.rest_between_ex = 0
if 'confirm_clear' not in st.session_state:
    st.session_state.confirm_clear = False
if 'last_update' not in st.session_state:
    st.session_state.last_update = time.time()

# ----------------------------
# Helper Functions
# ----------------------------

def load_workout_data():
    if os.path.exists(FILENAME):
        try:
            df = pd.read_csv(FILENAME)
            return df
        except:
            return pd.DataFrame(columns=REQUIRED_COLUMNS)
    return pd.DataFrame(columns=REQUIRED_COLUMNS)

def estimate_calories(exercise, seconds, category, weight_kg, note=""):
    met = MET_TABLE.get(exercise, DEFAULT_MET_BY_CATEGORY.get(category, 3.0))
    base_calories = met * 3.5 * weight_kg / 200 * (seconds / 60)
    note_lower = note.lower()
    if any(word in note_lower for word in ["very intense", "hard", "exhausted", "maximum"]):
        base_calories *= 1.1
    elif any(word in note_lower for word in ["easy", "light", "moderate"]):
        base_calories *= 0.9
    return round(base_calories, 2)

def save_workout_data():
    df = load_workout_data()
    next_id = (df["session_id"].max() + 1) if not df.empty else 1
    now = datetime.now()
    date_str, time_str = now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S")
    new_rows = []
    
    for item in st.session_state.session:
        kcal = estimate_calories(
            item["exercise"], item["seconds"], item["category"],
            st.session_state.weight_kg, st.session_state.note
        )
        new_rows.append({
            "session_id": next_id,
            "exercise": item["exercise"],
            "time_seconds": item["seconds"],
            "date": date_str,
            "time": time_str,
            "category": item["category"],
            "calories": kcal,
            "note": st.session_state.note,
            "weight_kg": st.session_state.weight_kg
        })
    
    if new_rows:
        new_df = pd.DataFrame(new_rows)
        new_df.to_csv(FILENAME, mode='a', header=not os.path.exists(FILENAME), index=False)
        st.success("Workout saved successfully! 🎉")

def reset_runtime_state(full=False):
    st.session_state.timer_running = False
    st.session_state.paused = False
    st.session_state.current_index = 0
    st.session_state.remaining_time = 0
    st.session_state.in_rest = False
    st.session_state.rest_remaining = 0
    st.session_state.workout_complete = False
    st.session_state.last_update = time.time()
    
    if full:
        st.session_state.session = []
        st.session_state.note = ""
        st.session_state.confirm_clear = False

def add_to_sequence(exercise, seconds, category):
    st.session_state.session.append({"exercise": exercise.strip(), "seconds": int(seconds), "category": category})
    st.success(f"Added {exercise} ({seconds}s)")

# ----------------------------
# Page Configuration
# ----------------------------
st.set_page_config(page_title="FitPulse", page_icon="🏃", layout="wide")

# ----------------------------
# Main Application
# ----------------------------
st.title("🏃 FitPulse Workout Tracker")

col1, col2 = st.columns([1, 2])

with col1:
    st.header("➕ Add Exercise")
    
    with st.expander("Settings", expanded=True):
        st.session_state.weight_kg = st.number_input("Weight (kg)", 25.0, 200.0, st.session_state.weight_kg, 0.5)
        st.session_state.rest_between_ex = st.number_input("Rest between exercises (s)", 0, 300, st.session_state.rest_between_ex, 5)

    categories = ["Cardio", "Strength", "Flexibility", "Other"]
    category = st.selectbox("Category", categories)
    
    common_exercises = {
        "Cardio": ["Running", "Cycling", "Jumping Jacks", "Burpees"],
        "Strength": ["Push-ups", "Squats", "Lunges", "Plank"],
        "Flexibility": ["Yoga Stretch", "Side Bends"],
        "Other": []
    }
    
    quick = st.selectbox("Quick pick", ["(Type custom)"] + common_exercises[category])
    exercise = st.text_input("Exercise Name", "" if quick == "(Type custom)" else quick)
    time_sec = st.number_input("Time (seconds)", 1, 3600, 60, 1)

    col_add, col_reset, col_clear = st.columns(3)
    if col_add.button("Add to Sequence", use_container_width=True):
        if exercise.strip():
            add_to_sequence(exercise, time_sec, category)
        else:
            st.error("Please enter exercise name")
    
    if col_reset.button("Reset Session", use_container_width=True):
        reset_runtime_state(full=True)
        st.success("Session reset!")
    
    if col_clear.button("Clear History", use_container_width=True):
        if st.session_state.confirm_clear:
            if os.path.exists(FILENAME):
                os.remove(FILENAME)
            st.success("History cleared!")
            st.session_state.confirm_clear = False
        else:
            st.session_state.confirm_clear = True
            st.warning("Click again to confirm")

    st.subheader("🧾 Workout Sequence")
    if st.session_state.session:
        for i, item in enumerate(st.session_state.session):
            st.write(f"{i+1}. {item['exercise']} - {item['seconds']}s")
    else:
        st.info("No exercises added")

    st.subheader("📝 Session Note")
    st.session_state.note = st.text_area("Notes", st.session_state.note, placeholder="How did you feel?")

    col_start, col_pause, col_chart = st.columns(3)
    if col_start.button("▶️ Start", use_container_width=True, disabled=not st.session_state.session):
        st.session_state.timer_running = True
        st.session_state.remaining_time = st.session_state.session[0]["seconds"]
    
    if col_pause.button("⏸️ Pause", use_container_width=True, disabled=not st.session_state.timer_running):
        st.session_state.paused = not st.session_state.paused
    
    if col_chart.button("📊 Charts", use_container_width=True):
        st.session_state.show_chart = not st.session_state.show_chart

with col2:
    st.header("🏁 Workout Progress")
    
    # Timer logic
    current_time = time.time()
    if (st.session_state.timer_running and not st.session_state.paused and 
        current_time - st.session_state.last_update >= 1.0):
        st.session_state.last_update = current_time
        st.rerun()
    
    if st.session_state.workout_complete:
        st.balloons()
        st.success("Workout Complete! 🎉")
        if st.button("New Session"):
            reset_runtime_state(full=True)
    
    elif st.session_state.timer_running and st.session_state.session:
        idx = st.session_state.current_index
        item = st.session_state.session[idx]
        
        if st.session_state.in_rest:
            st.subheader("🛌 Rest")
            st.metric("Time Remaining", f"{st.session_state.rest_remaining}s")
        else:
            st.metric(item["exercise"], f"{st.session_state.remaining_time}s", f"{idx+1}/{len(st.session_state.session)}")
            st.progress(1 - st.session_state.remaining_time / item["seconds"])
        
    else:
        st.info("Add exercises and click Start")

# Charts Section
if st.session_state.show_chart:
    st.markdown("---")
    df = load_workout_data()
    if not df.empty:
        st.subheader("📈 Analytics")
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Workouts", df["session_id"].nunique())
        total_sec = df["time_seconds"].sum()
        col2.metric("Total Time", f"{total_sec//60}m")
        col3.metric("Calories", f"{df['calories'].sum():.0f}")
        
        st.subheader("Exercise Distribution")
        fig, ax = plt.subplots()
        df.groupby("exercise")["time_seconds"].sum().plot(kind="barh", ax=ax)
        st.pyplot(fig)
        
        if st.button("Download CSV"):
            csv = df.to_csv(index=False).encode()
            st.download_button("Download", csv, "workouts.csv")
    else:
        st.info("No workout data yet")
