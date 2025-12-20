from datetime import timedelta
from functools import lru_cache

# ----------------------------
# Constants and Models
# ----------------------------
MET_VALUES = {
    "Running": 9.8, "Cycling": 7.5, "Jumping Jacks": 8.0, "Burpees": 8.8,
    "Push-ups": 8.0, "Squats": 5.0, "Lunges": 5.0, "Plank": 3.3,
    "Yoga": 2.5, "Stretching": 2.8, "Weightlifting": 6.0, "Swimming": 7.0,
    "Walking": 4.0, "Rowing": 7.0, "HIIT": 9.0, "Pilates": 3.5
}

WORKOUT_PROGRAMS = {
    "Beginner Full Body": [
        {"exercise": "Push-ups", "duration": 30},
        {"exercise": "Squats", "duration": 30},
        {"exercise": "Plank", "duration": 30},
        {"exercise": "Lunges", "duration": 30}
    ],
    "Quick HIIT": [
        {"exercise": "Burpees", "duration": 20},
        {"exercise": "Jumping Jacks", "duration": 20},
        {"exercise": "Mountain Climbers", "duration": 20}
    ]
}

# ----------------------------
# Helper Functions
# ----------------------------
@lru_cache(maxsize=128)
def calculate_calories(exercise: str, seconds: int) -> float:
    """
    Calculate calories burned for an exercise.
    Uses fixed weight of 70kg for calculations.
    """
    met = MET_VALUES.get(exercise, 5.0)
    weight = 70.0  # Fixed weight
    return round(met * 3.5 * weight / 200 * (seconds / 60), 2)

def format_time(seconds: int) -> str:
    """Format seconds into MM:SS format"""
    return str(timedelta(seconds=seconds)).split(".")[0].zfill(5)
