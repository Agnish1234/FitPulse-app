import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
import os
import time
from streamlit_autorefresh import st_autorefresh

# ----------------------------
# Page Configuration
# ----------------------------
st.set_page_config(
    page_title="FitPulse - Workout Tracker",
    page_icon="🏃",
    layout="wide"
)

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
        'weight_kg': 70.0,
        'rest_time': 60,
        'notes': "",
        'workout_complete': False
    }

# ----------------------------
# Auto-refresh for timer
# ----------------------------
if st.session_state.workout_data['timer_running'] and not st.session_state.workout_data['paused']:
    st_autorefresh(interval=1000, limit=100, key="timer_refresh")

# ----------------------------
# Helper Functions
# ----------------------------
MET_VALUES = {
    "Running": 9.8, "Cycling": 7.5, "Jumping Jacks": 8.0, "Burpees": 8.8,
    "Push-ups": 8.0, "Squats": 5.0, "Lunges": 5.0, "Plank": 3.3,
    "Yoga": 2.5, "Stretching": 2.8
}

def calculate_calories(exercise, seconds, weight):
    met = MET_VALUES.get(exercise, 5.0)
    return round(met * 3.5 * weight / 200 * (seconds / 60), 2)

def save_workout():
    if not st.session_state.workout_data['exercises']:
        st.warning("No exercises to save!")
        return
        
    try:
        workout_df = pd.DataFrame(st.session_state.workout_data['exercises'])
        workout_df['timestamp'] = datetime.now()
        workout_df['total_calories'] = workout_df.apply(
            lambda row: calculate_calories(row['exercise'], row['duration'], st.session_state.workout_data['weight_kg']),
            axis=1
        )
        
        if os.path.exists('workouts.csv'):
            workout_df.to_csv('workouts.csv', mode='a', header=False, index=False)
        else:
            workout_df.to_csv('workouts.csv', index=False)
        
        st.success("✅ Workout saved successfully! 🎉")
    except Exception as e:
        st.error(f"Error saving workout: {e}")

def reset_workout():
    st.session_state.workout_data = {
        'exercises': [],
        'timer_running': False,
        'paused': False,
        'current_index': 0,
        'remaining_time': 0,
        'weight_kg': 70.0,
        'rest_time': 60,
        'notes': "",
        'workout_complete': False
    }
    st.success("🔄 Workout reset successfully!")

def clear_workout_data():
    """Clear all saved workout data from CSV file"""
    if os.path.exists('workouts.csv'):
        os.remove('workouts.csv')
        st.success("🗑️ All workout data cleared successfully!")
    else:
        st.info("No workout data found to clear.")

# ----------------------------
# Timer Update Function
# ----------------------------
def update_timer():
    """Update the timer countdown"""
    data = st.session_state.workout_data
    
    if data['timer_running'] and not data['paused']:
        data['remaining_time'] -= 1
        
        # Check if current exercise is complete
        if data['remaining_time'] <= 0:
            data['current_index'] += 1
            
            if data['current_index'] < len(data['exercises']):
                # Start next exercise
                data['remaining_time'] = data['exercises'][data['current_index']]['duration']
            else:
                # Workout complete
                data['timer_running'] = False
                data['workout_complete'] = True
                save_workout()
                st.balloons()

# ----------------------------
# Application UI
# ----------------------------
st.title("🏃 FitPulse Workout Tracker")
st.divider()

# Update timer on each refresh
if st.session_state.workout_data['timer_running'] and not st.session_state.workout_data['paused']:
    update_timer()

col1, col2 = st.columns([1, 2])

with col1:
    st.header("➕ Add Exercise")

    with st.expander("⚙️ Settings", expanded=True):
        st.session_state.workout_data['weight_kg'] = st.number_input(
            "Your Weight (kg)", 40.0, 150.0, st.session_state.workout_data['weight_kg'], 1.0
        )
        st.session_state.workout_data['rest_time'] = st.number_input(
            "Rest between exercises (seconds)", 0, 300, st.session_state.workout_data['rest_time'], 10
        )

    exercise_name = st.text_input("Exercise Name", "Running")
    exercise_duration = st.slider("Duration (seconds)", 10, 3600, 60, 10)

    if st.button("➕ Add Exercise", key="add_exercise", use_container_width=True):
        st.session_state.workout_data['exercises'].append({
            'exercise': exercise_name,
            'duration': exercise_duration
        })
        st.success(f"✅ Added {exercise_name} for {exercise_duration}s")

    st.subheader("🧾 Exercises")
    if st.session_state.workout_data['exercises']:
        for idx, ex in enumerate(st.session_state.workout_data['exercises']):
            calories = calculate_calories(ex['exercise'], ex['duration'], st.session_state.workout_data['weight_kg'])
            st.write(f"{idx+1}. **{ex['exercise']}** - {ex['duration']}s (🔥 {calories} cal)")
    else:
        st.info("No exercises added yet.")

    st.subheader("📝 Notes")
    st.session_state.workout_data['notes'] = st.text_area(
        "How did you feel?",
        st.session_state.workout_data['notes'],
        placeholder="Great workout! Felt strong today...",
        height=100
    )

    st.subheader("🎛 Controls")
    c1, c2, c3, c4 = st.columns(4)

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

    # Clear Data Button
    if c4.button("🗑️ Clear Data", use_container_width=True):
        clear_workout_data()

with col2:
    st.header("🏁 Workout Progress")
    st.divider()

    data = st.session_state.workout_data
    exercises = data['exercises']
    
    if data['timer_running']:
        idx = data['current_index']
        if idx < len(exercises):
            current = exercises[idx]
            
            # Display current exercise with timer
            col1, col2 = st.columns([2, 1])
            with col1:
                st.metric(
                    f"Exercise {idx+1}/{len(exercises)}", 
                    f"{data['remaining_time']}s", 
                    current['exercise']
                )
            with col2:
                status = "⏸️ Paused" if data['paused'] else "▶️ Running"
                st.metric("Status", status)
            
            # Progress bar
            progress = 1 - (data['remaining_time'] / current['duration'])
            st.progress(progress)

            # Calories estimation
            calories = calculate_calories(current['exercise'], current['duration'], data['weight_kg'])
            st.caption(f"🔥 Estimated calories: {calories}")

        else:
            data['timer_running'] = False
            data['workout_complete'] = True
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
    else:
        st.info("Add some exercises to get started! 🏃‍♂️")

# ----------------------------
# Progress Chart Section
# ----------------------------
if st.session_state.workout_data['exercises']:
    st.divider()
    st.subheader("📊 Progress Chart")
    
    exercises = st.session_state.workout_data['exercises']
    total_time = sum(ex['duration'] for ex in exercises)
    total_calories = sum(calculate_calories(ex['exercise'], ex['duration'], st.session_state.workout_data['weight_kg']) for ex in exercises)

    col1, col2, col3 = st.columns(3)
    col1.metric("Exercises", len(exercises))
    col2.metric("Total Time", f"{total_time // 60}m {total_time % 60}s")
    col3.metric("Total Calories", f"{total_calories:.0f}")

    # Chart - FIXED
    if exercises:
        try:
            # Create exercise duration data
            exercise_data = []
            for ex in exercises:
                exercise_data.append({
                    'Exercise': ex['exercise'],
                    'Duration': ex['duration'],
                    'Calories': calculate_calories(ex['exercise'], ex['duration'], st.session_state.workout_data['weight_kg'])
                })
            
            chart_df = pd.DataFrame(exercise_data)
            
            # Create the chart
            fig, ax = plt.subplots(figsize=(10, 6))
            bars = ax.barh(chart_df['Exercise'], chart_df['Duration'], color='skyblue')
            ax.set_xlabel('Duration (seconds)')
            ax.set_title('Exercise Duration Distribution')
            
            # Add value labels on bars
            for bar in bars:
                width = bar.get_width()
                ax.text(width + 5, bar.get_y() + bar.get_height()/2, 
                       f'{int(width)}s', ha='left', va='center')
            
            plt.tight_layout()
            st.pyplot(fig)
            
        except Exception as e:
            st.error(f"Error creating chart: {e}")

# ----------------------------
# Footer
# ----------------------------
st.divider()
st.caption("💪 FitPulse - Your personal workout tracker | Timer Working! 🚀")