# main.py
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
import os
from typing import List, Dict, Any
from streamlit_autorefresh import st_autorefresh

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
    'confirm_clear': False
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
                st.warning(f"Missing columns in data file: {missing_cols}. Returning empty data.")
                return pd.DataFrame(columns=REQUIRED_COLUMNS)
            return df
        except Exception as e:
            st.error(f"Error reading workout data: {e}")
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
            st.toast("Workout saved successfully! 🎉", icon="✅")
        except Exception as e:
            st.error(f"Failed to save workout data: {e}")

def reset_runtime_state(full: bool = False) -> None:
    keys_to_reset = ['timer_running', 'paused', 'current_index', 'remaining_time', 'in_rest', 'rest_remaining', 'workout_complete']
    for key in keys_to_reset:
        st.session_state[key] = DEFAULTS[key]
    if full:
        st.session_state.session = []
        st.session_state.note = ""
        st.session_state.confirm_clear = False

def add_to_sequence(exercise: str, seconds: int, category: str) -> None:
    st.session_state.session.append({"exercise": exercise.strip(), "seconds": int(seconds), "category": category})
    st.toast(f"Added '{exercise}' to sequence.", icon="✅")

# ----------------------------
# Page config
# ----------------------------
st.set_page_config(page_title="FitPulse", page_icon="🏃", layout="wide")

# ----------------------------
# UI Layout with wider columns
# ----------------------------

col1, col2 = st.columns([1, 3])  # Wider right panel

with col1:
    st.header("➕ Add Exercise")
    with st.expander("Settings", expanded=True):
        st.session_state.weight_kg = st.number_input(
            "Weight (kg)", 25.0, 200.0, st.session_state.weight_kg, 0.5, key="weight_input"
        )
        st.session_state.rest_between_ex = st.number_input(
            "Rest between exercises (s)", 0, 300, st.session_state.rest_between_ex, 5, key="rest_input"
        )

    categories = ["Cardio", "Strength", "Flexibility", "Other"]
    category = st.selectbox("Category", categories, index=categories.index(st.session_state.get('cat_select', 'Cardio')), key='cat_select')

    common_by_cat = {
        "Cardio": ["Running", "Cycling", "Jumping Jacks", "Burpees", "Mountain Climbers", "Skipping", "Rowing"],
        "Strength": ["Push-ups", "Squats", "Lunges", "Plank"],
        "Flexibility": ["Yoga Stretch", "Side Bends"],
        "Other": []
    }
    quick = st.selectbox("Quick pick", ["(Type custom)"] + common_by_cat[category], index=0, key='quick_pick')

    exercise = st.text_input("Exercise Name", "" if quick == "(Type custom)" else quick, key='ex_input')
    time_sec = st.number_input("Time (seconds)", 1, MAX_TIME_SECONDS, 60, 1, key='time_input')

    c_add, c_reset, c_clear = st.columns(3)
    if c_add.button("Add to Sequence", use_container_width=True):
        if exercise.strip():
            add_to_sequence(exercise, time_sec, category)
        else:
            st.error("Please enter a valid exercise name.")

    if c_reset.button("Reset Session", use_container_width=True):
        reset_runtime_state(full=True)
        st.toast("Session reset.", icon="🔄")

    if c_clear.button("🗑 Clear History", use_container_width=True):
        if st.session_state.confirm_clear:
            if os.path.exists(FILENAME):
                try:
                    os.remove(FILENAME)
                    st.toast("Workout history cleared!", icon="⚠️")
                except Exception as e:
                    st.error(f"Failed to clear history: {e}")
            else:
                st.info("No history file found to clear.")
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

    st.subheader("📝 Session Note (Important!)")
    st.session_state.note = st.text_area(
        "Your thoughts, feelings, or intensity of workout",
        st.session_state.note,
        placeholder="How did you feel? This will be saved with the session.",
        key='note_input'
    )

    col_controls = st.columns(3)
    start_disabled = not st.session_state.session
    if col_controls[0].button("▶️ Start Workout", use_container_width=True, disabled=start_disabled):
        st.session_state.timer_running = True
        st.session_state.current_index = 0
        st.session_state.remaining_time = st.session_state.session[0]["seconds"]
        st.session_state.workout_complete = False
        st.session_state.in_rest = False
        st.session_state.rest_remaining = 0
        st.session_state.paused = False
    if start_disabled:
        st.caption("_Add exercises to enable Start_")

    if col_controls[1].button("⏸️ Pause/Resume", use_container_width=True, disabled=not st.session_state.timer_running):
        st.session_state.paused = not st.session_state.paused

    chart_button_label = "📊 Hide Chart" if st.session_state.show_chart else "📊 Show Chart"
    if col_controls[2].button(chart_button_label, use_container_width=True):
        st.session_state.show_chart = not st.session_state.show_chart

# ----------------------------
# Auto-refresh for timer
# ----------------------------
if st.session_state.timer_running and not st.session_state.paused:
    st_autorefresh(interval=1000, limit=100, key="timer_refresh")

# ----------------------------
# Right Panel - Workout Timer
# ----------------------------
with col2:
    st.header("🏁 Workout Progress")

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
            st.warning("Workout session index out of range. Resetting session.")
            reset_runtime_state(full=True)
        else:
            item = session[idx]
            ex, total_sec = item["exercise"], item["seconds"]

            if st.session_state.in_rest:
                st.subheader("🛌 Rest")
                st.metric("Rest Remaining", f"{st.session_state.rest_remaining}s")
                if not st.session_state.paused:
                    if st.session_state.rest_remaining > 0:
                        st.session_state.rest_remaining -= 1
                    else:
                        st.session_state.in_rest = False
                        st.session_state.current_index += 1
                        if st.session_state.current_index >= len(session):
                            st.session_state.timer_running = False
                            st.session_state.workout_complete = True
                            save_workout_data()
                        else:
                            next_item = session[st.session_state.current_index]
                            st.session_state.remaining_time = next_item["seconds"]

            else:
                st.metric(f"{ex} [{item['category']}]", f"{st.session_state.remaining_time}s", f"{idx+1}/{len(session)}")
                st.progress(1 - (st.session_state.remaining_time / total_sec))
                est_cal = estimate_calories(ex, total_sec, item['category'], st.session_state.weight_kg, st.session_state.note)
                st.caption(f"Est. Calories: ~{est_cal} kcal")

                if not st.session_state.paused:
                    if st.session_state.remaining_time > 0:
                        st.session_state.remaining_time -= 1
                    else:
                        if st.session_state.rest_between_ex > 0 and (idx + 1) < len(session):
                            st.session_state.in_rest = True
                            st.session_state.rest_remaining = st.session_state.rest_between_ex
                        else:
                            st.session_state.current_index += 1
                            if st.session_state.current_index >= len(session):
                                st.session_state.timer_running = False
                                st.session_state.workout_complete = True
                                save_workout_data()
                            else:
                                next_item = session[st.session_state.current_index]
                                st.session_state.remaining_time = next_item["seconds"]
    else:
        st.info("Workout paused. Click 'Resume' to continue.")

# ----------------------------
# Charts & Export Section
# ----------------------------
if st.session_state.show_chart:
    st.markdown("---")
    df = load_workout_data()
    if not df.empty:
        st.subheader("📈 Workout History")

        col_met1, col_met2, col_met3 = st.columns(3)
        with col_met1:
            st.metric("Total Workouts", df["session_id"].nunique())
        with col_met2:
            total_sec = int(df["time_seconds"].sum())
            st.metric("Total Time", f"{total_sec//60} min {total_sec%60}s")
        with col_met3:
            st.metric("Total Calories", f"{round(df['calories'].sum(), 1)} kcal")

        st.subheader("🏷 Exercise Distribution (Total Time)")
        fig, ax = plt.subplots(figsize=(10, 5))
        grouped = df.groupby("exercise")["time_seconds"].sum().sort_values(ascending=True)
        colors = [
            "#FF9999" if any("very intense" in str(n).lower() for n in df[df["exercise"] == ex]["note"]) else "#66B2FF"
            for ex in grouped.index
        ]
        grouped.plot(kind="barh", ax=ax, color=colors)
        ax.set_xlabel("Total Time (seconds)")
        plt.tight_layout()
        st.pyplot(fig)

        st.subheader("📥 Export Data")
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("Download CSV", csv, "workouts.csv", "text/csv")

    else:
        st.info("No workout data available yet. Complete a session to see charts.")
