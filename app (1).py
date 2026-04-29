from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import date, timedelta
import math

app = Flask(__name__)
CORS(app)

def get_first_monday(d):
    """Get the first Monday on or after a given date."""
    days_until_monday = (7 - d.weekday()) % 7
    if days_until_monday == 0:
        return d
    return d + timedelta(days=days_until_monday)

def get_final_week_monday(race_date):
    """Get the Monday of the week containing the race date."""
    days_since_monday = race_date.weekday()  # 0=Monday, 6=Sunday
    return race_date - timedelta(days=days_since_monday)

def format_date(d):
    """Format date as 'Jun 2' or 'Oct 14'."""
    return d.strftime("%b %-d")

def parse_date(date_str):
    """Parse date string in various formats."""
    from datetime import datetime
    formats = [
        "%B %d, %Y",   # November 22, 2026
        "%B %d %Y",    # November 22 2026
        "%b %d, %Y",   # Nov 22, 2026
        "%Y-%m-%d",    # 2026-11-22
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Cannot parse date: {date_str}")

DISTANCE_LIMITS = {
    "sprint":       {"min": 8,  "max": 12},
    "olympic":      {"min": 12, "max": 16},
    "half ironman": {"min": 16, "max": 24},
    "full ironman": {"min": 20, "max": 32},
}

def get_distance_key(race_distance):
    """Normalize race distance string to key."""
    rd = race_distance.lower()
    if "sprint" in rd:
        return "sprint"
    elif "olympic" in rd:
        return "olympic"
    elif "half" in rd or "70.3" in rd:
        return "half ironman"
    elif "full" in rd or "140.6" in rd or "ironman" in rd:
        return "full ironman"
    return "full ironman"

def get_taper_weeks(distance_key):
    """Get number of taper weeks by distance."""
    if distance_key in ["sprint", "olympic"]:
        return 1
    return 2

@app.route("/calculate", methods=["POST"])
def calculate():
    try:
        data = request.get_json(force=True, silent=False)
        if data is None:
            return jsonify({"error": "No JSON received", "content_type": request.content_type, "raw": request.get_data(as_text=True)[:200]}), 400

        race_date_str = data.get("race_date", "")
        generated_date_str = data.get("generated_date", "")
        race_distance = data.get("race_distance", "Full Ironman 140.6")

        # Parse dates
        race_date = parse_date(race_date_str)
        generated_date = parse_date(generated_date_str)

        # Get distance limits
        distance_key = get_distance_key(race_distance)
        limits = DISTANCE_LIMITS[distance_key]
        taper_weeks = get_taper_weeks(distance_key)

        # Calculate final week Monday
        final_week_monday = get_final_week_monday(race_date)

        # Calculate first Monday on or after generated date
        first_monday = get_first_monday(generated_date)

        # Calculate total weeks (inclusive of race week)
        days_between = (final_week_monday - first_monday).days
        total_weeks = (days_between // 7) + 1

        # Apply distance limits
        compressed = False
        if total_weeks > limits["max"]:
            total_weeks = limits["max"]
        elif total_weeks < limits["min"]:
            compressed = True

        # Calculate Week 1 Monday
        week1_monday = final_week_monday - timedelta(weeks=total_weeks - 1)

        # Derive race day of week
        days_of_week = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        race_day_of_week = days_of_week[race_date.weekday()]

        # Calculate taper week number
        taper_week_number = total_weeks - taper_weeks + 1
        taper_week = f"Week {taper_week_number}"

        # Build compressed timeline message
        if compressed:
            compressed_message = (
                f"Your race date gives you {total_weeks} weeks to train. "
                f"The recommended minimum for a {race_distance} is {limits['min']} weeks. "
                f"We have built you the best plan possible in the time available "
                f"but be aware this is a compressed timeline."
            )
        else:
            compressed_message = ""

        # Build all 32 week dates
        week_dates = {}
        for wk in range(1, 33):
            wk_str = f"{wk:02d}"
            if wk <= total_weeks:
                monday = week1_monday + timedelta(weeks=wk - 1)
                week_dates[f"WK{wk_str}_D1"] = format_date(monday)
                week_dates[f"WK{wk_str}_D2"] = format_date(monday + timedelta(days=1))
                week_dates[f"WK{wk_str}_D3"] = format_date(monday + timedelta(days=2))
                week_dates[f"WK{wk_str}_D4"] = format_date(monday + timedelta(days=3))
                week_dates[f"WK{wk_str}_D5"] = format_date(monday + timedelta(days=4))
                week_dates[f"WK{wk_str}_D6"] = format_date(monday + timedelta(days=5))
                week_dates[f"WK{wk_str}_D7"] = format_date(monday + timedelta(days=6))
            else:
                week_dates[f"WK{wk_str}_D1"] = ""
                week_dates[f"WK{wk_str}_D2"] = ""
                week_dates[f"WK{wk_str}_D3"] = ""
                week_dates[f"WK{wk_str}_D4"] = ""
                week_dates[f"WK{wk_str}_D5"] = ""
                week_dates[f"WK{wk_str}_D6"] = ""
                week_dates[f"WK{wk_str}_D7"] = ""

        # Build calendar summary -- single string for Claude
        lines = [
            "PRE-CALCULATED CALENDAR DATA -- USE THESE EXACTLY, DO NOT RECALCULATE:",
            f"TOTAL_WEEKS: {total_weeks}",
            f"TAPER_WEEK: {taper_week}",
            f"RACE_DAY_OF_WEEK: {race_day_of_week}",
            f"COMPRESSED_TIMELINE: {'true' if compressed else 'false'}",
            f"COMPRESSED_TIMELINE_MESSAGE: {compressed_message}",
            f"WEEK_1_MONDAY: {format_date(week1_monday)}",
            f"FINAL_WEEK_MONDAY: {format_date(final_week_monday)}",
            "",
            "WEEK DATES -- COPY THESE EXACTLY INTO WKxx_Dx FIELDS:",
        ]
        for wk in range(1, 33):
            wk_str = f"{wk:02d}"
            if wk <= total_weeks:
                monday = week1_monday + timedelta(weeks=wk - 1)
                d1 = format_date(monday)
                d2 = format_date(monday + timedelta(days=1))
                d3 = format_date(monday + timedelta(days=2))
                d4 = format_date(monday + timedelta(days=3))
                d5 = format_date(monday + timedelta(days=4))
                d6 = format_date(monday + timedelta(days=5))
                d7 = format_date(monday + timedelta(days=6))
                lines.append(f"WK{wk_str}: D1={d1} D2={d2} D3={d3} D4={d4} D5={d5} D6={d6} D7={d7}")
            else:
                lines.append(f"WK{wk_str}: D1= D2= D3= D4= D5= D6= D7=")

        calendarsummary = "\n".join(lines)

        # Build response
        result = {
            "total_weeks": str(total_weeks),
            "taper_week": taper_week,
            "taper_week_number": str(taper_week_number),
            "race_day_of_week": race_day_of_week,
            "week1_monday": format_date(week1_monday),
            "final_week_monday": format_date(final_week_monday),
            "compressed_timeline": "true" if compressed else "false",
            "compressed_timeline_message": compressed_message,
            "calendarsummary": calendarsummary,
            **week_dates
        }

        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "CustomTRI Date Calculator"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
