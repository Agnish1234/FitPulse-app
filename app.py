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
# Session State Defaults
# ----------------------------
DEFAULTS = {
    'session': [],
    'timer_running': False,
    'paused': False,
    'current_index': 0,
    'remaining_time': 0,
    'in_rest': False,
    'rest_remaining': 0,
    'workout_complete': False,
    'show_chart': False,
    'note': "",
    'weight_kg': DEFAULT_WEIGHT_KG,
    'rest_between_ex': 0,
    'confirm_clear': False,
    'last_update': time.time()
}

for key, val in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = val

# ----------------------------
# Helper Functions
# ----------------------------

def load_workout_data() -> pd.DataFrame:
    if os.path.exists(FILENAME):
        try:
            df = pd.read_csv(FILENAME)
            missing_cols = [col for col in REQUIRED_COLUMNS if col not in df.columns]
            if missing_cols:
                return pd.DataFrame(columns=REQUIRED_COLUMNS)
            return df
        except Exception as e:
            return pd.DataFrame(columns=REQUIRED_COLUMNS)
    return pd.DataFrame(columns=REQUIRED_COLUMNS)

def estimate_calories(exercise: str, seconds: int, category: str, weight_kg: float, note: str = "") -> float:
    met = MET_TABLE.get(exercise, DEFAULT_MET_BY_CATEGORY.get(category, 3.0))
    base_calories = met * 3.5 * weight_kg / 200 * (seconds / 60)
    note_lower = note.lower()
    if any(word in note_lower for word in ["very intense", "hard", "exhausted", "maximum"]):
        base_calories *= 1.1
    elif any(word in note_lower for word in ["easy", "light", "moderate"]):
        base_calories *= 0.9
    return round(base_calories, 2)

def save_workout_data() -> None:
    now = datetime.now()
    date_str, time_str = now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S")
    new_rows: List[Dict[str, Any]] = []

    existing_df = load_workout_data()
    next_id = existing_df["session_id"].max() + 1 if not existing_df.empty else 1

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
        try:
            new_df.to_csv(FILENAME, mode='a', header=not os.path.exists(FILENAME), index=False)
            st.success("Workout saved successfully! 🎉")
        except Exception as e:
            st.error(f"Failed to save workout data: {e}")

def reset_runtime_state(full: bool = False) -> None:
    keys_to_reset = ['timer_running', 'paused', 'current_index', 'remaining_time', 'in_rest', 'rest_remaining', 'workout_complete', 'last_update']
    for key in keys_to_reset:
        st.session_state[key] = DEFAULTS[key]
    if full:
        st.session_state.session = []
        st.session_state.note = ""
        st.session_state.confirm_clear = False

def add_to_sequence(exercise: str, seconds: int, category: str) -> None:
    st.session_state.session.append({"exercise": exercise.strip(), "seconds": int(seconds), "category": category})
    st.success(f"Added '{exercise}' to sequence.")

# ----------------------------
# Timer Auto-Refresh Logic
# ----------------------------
def handle_timer_refresh():
    """Handle timer updates without external dependencies"""
    current_time = time.time()
    if (st.session_state.timer_running and 
        not st.session_state.paused and 
        current_time - st.session_state.last_update >= 1.0):
        
        st.session_state.last_update = current_time
        return True
    return False

# ----------------------------
# Page config
# ----------------------------
st.set_page_config(page_title="FitPulse", page_icon="🏃", layout="wide")

# ----------------------------
# UI Layout
# ----------------------------
col1, col2 = st.columns([1, 3])

with col1:
    st.header("➕ Add Exercise")
    with st.expander("Settings", expanded=True):
        st.session_state.weight_kg = st.number_input(
            "Weight (kg)", 25.0, 200.0, st.session_state.weight_kg, 0.5
        )
        st.session_state.rest_between_ex = st.number_input(
            "Rest between exercises (s)", 0, 300, st.session_state.rest_between_ex, 5
        )

    categories = ["Cardio", "Strength", "Flexibility", "Other"]
    category = st.selectbox("Category", categories)

    common_by_cat = {
        "Cardio": ["Running", "Cycling", "Jumping Jacks", "Burpees", "Mountain Climbers", "Skipping", "Rowing"],
        "Strength": ["Push-ups", "Squats", "Lunges", "Plank"],
        "Flexibility": ["Yoga Stretch", "Side Bends"],
        "Other": []
    }
    quick = st.selectbox("Quick pick", ["(Type custom)"] + common_by_cat[category])

    exercise = st.text_input("Exercise Name", "" if quick == "(Type custom)" else quick)
    time_sec = st.number_input("Time (seconds)", 1, MAX_TIME_SECONDS, 60, 1)

    c_add, c_reset, c_clear = st.columns(3)
    if c_add.button("Add to Sequence", use_container_width=True):
        if exercise.strip():
            add_to_sequence(exercise, time_sec, category)
        else:
            st.error("Please enter a valid exercise name.")

    if c_reset.button("Reset Session", use_container_width=True):
        reset_runtime_state(full=True)
        st.success("Session reset!")

    if c_clear.button("🗑 Clear History", use_container_width=True):
        if st.session_state.confirm_clear:
            if os.path.exists(FILENAME):
                try:
                    os.remove(FILENAME)
                    st.success("Workout history cleared!")
                except Exception as e:
                    st.error(f"Failed to clear history: {e}")
            st.session_state.confirm_clear = False
        else:
            st.session_state.confirm_clear = True
            st.warning("Click again to confirm permanent deletion of ALL history.")

    if st.session_state.confirm_clear:
        st.warning("Click 'Clear History' again to confirm.")

    st.subheader("🧾 Workout Sequence")
    if st.session_state.session:
        for i, item in enumerate(st.session_state.session):
            st.write(f"{i+1}. {item['exercise']} - {item['seconds']}s [{item['category']}]")
    else:
        st.info("No exercises added yet.")

    st.subheader("📝 Session Note")
    st.session_state.note = st.text_area(
        "Your thoughts, feelings, or intensity of workout",
        st.session_state.note,
        placeholder="How did you feel? This will be saved with the session.",
        height=100
    )

    col_controls = st.columns(3)
    start_disabled = not st.session_state.session
    if col_controls[0].button("▶️ Start Workout", use_container_width=True, disabled=start_disabled):
        st.session_state.timer_running = True
        st.session_state.current_index = 0
        st.session_state.remaining_time = st.session_state.session[0]["seconds"]
        st.session_state.workout_complete = False
        st.session_state.last_update = time.time()
    
    if col_controls[1].button("⏸️ Pause/Resume", use_container_width=True, disabled=not st.session_state.timer_running):
        st.session_state.paused = not st.session_state.paused
        st.session_state.last_update = time.time()

    chart_button_label = "📊 Hide Chart" if st.session_state.show_chart else "📊 Show Chart"
    if col_controls[2].button(chart_button_label, use_container_width=True):
        st.session_state.show_chart = not st.session_state.show_chart

# ----------------------------
# Right Panel - Workout Timer
# ----------------------------
with col2:
    st.header("🏁 Workout Progress")

    # Handle timer refresh
    if handle_timer_refresh():
        st.rerun()

    if st.session_state.workout_complete:
        st.balloons()
        st.success("Workout Complete! 🎉")
        if st.button("Start New Session"):
            reset_runtime_state(full=True)

    elif not st.session_state.session:
        st.info("Add exercises and click 'Start Workout' to begin.")

    elif st.session_state.timer_running:
        idx = st.session_state.current_index
        session = st.session_state.session

        if not (0 <= idx < len(session)):
            st.error("Workout session error. Resetting...")
            reset_runtime_state(full=True)
        else:
            item = session[idx]
            ex, total_sec = item["exercise"], item["seconds"]

            if st.session_state.in_rest:
                st.subheader("🛌 Rest")
                st.metric("Rest Remaining", f"{st.session_state.rest_remaining}s")
                if not st.session_state.paused and st.session_state.rest_remaining > 0:
                    st.session_state.rest_remaining -= 1

            else:
                st.metric(f"{ex} [{item['category']}]", f"{st.session_state.remaining_time}s", f"{idx+1}/{len(session)}")
                st.progress(1 - (st.session_state.remaining_time / total_sec))
                est_cal = estimate_calories(ex, total_sec, item['category'], st.session_state.weight_kg, st.session_state.note)
                st.caption(f"Est. Calories: ~{est_cal} kcal")

                if not st.session_state.paused and st.session_state.remaining_time > 0:
                    st.session_state.remaining_time -= 1

        # Handle exercise completion
        if not st.session_state.paused:
            if st.session_state.in_rest and st.session_state.rest_remaining <= 0:
                st.session_state.in_rest = False
                st.session_state.current_index += 1
                if st.session_state.current_index < len(session):
                    st.session_state.remaining_time = session[st.session_state.current_index]["seconds"]
                else:
                    st.session_state.timer_running = False
                    st.session_state.workout_complete = True
                    save_workout_data()
            
            elif not st.session_state.in_rest and st.session_state.remaining_time <= 0:
                if st.session_state.rest_between_ex > 0 and (idx + 1) < len(session):
                    st.session_state.in_rest = True
                    st.session_state.rest_remaining = st.session_state.rest_between_ex
                else:
                    st.session_state.current_index += 1
                    if st.session_state.current_index < len(session):
                        st.session_state.remaining_time = session[st.session_state.current_index]["seconds"]
                    else:
                        st.session_state.timer_running = False
                        st.session_state.workout_complete = True
                        save_workout_data()
    else:
        st.info("Workout paused. Click 'Resume' to continue.")

# ----------------------------
# Charts & Analytics
# ----------------------------
if st.session_state.show_chart:
    st.markdown("---")
    df = load_workout_data()
    if not df.empty:
        st.subheader("📈 Workout History")

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Workouts", df["session_id"].nunique())
        with col2:
            total_sec = int(df["time_seconds"].sum())
            st.metric("Total Time", f"{total_sec//60}m {total_sec%60}s")
        with col3:
            st.metric("Total Calories", f"{df['calories'].sum():.1f} kcal")

        st.subheader("🏷 Exercise Distribution")
        fig, ax = plt.subplots(figsize=(10, 6))
        exercise_time = df.groupby("exercise")["time_seconds"].sum().sort_values(ascending=True)
        exercise_time.plot(kind="barh", ax=ax, color="#FF4B4B")
        ax.set_xlabel("Total Time (seconds)")
        plt.tight_layout()
        st.pyplot(fig)

        st.subheader("📥 Export Data")
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("Download CSV", csv, "workout_history.csv", "text/csv")

    else:
        st.info("No workout data available yet. Complete a session to see analytics.")

