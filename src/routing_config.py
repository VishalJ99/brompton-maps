#!/usr/bin/env python3
"""
ABOUTME: Configuration parameters for customizable bike+tube routing
ABOUTME: Defines cycle speeds, wait times, and buffer calculations
"""

# Cycling parameters
DEFAULT_CYCLE_SPEED_KMH = 15.0  # Realistic urban cycling speed
MIN_CYCLE_SPEED_KMH = 8.0  # Minimum allowed speed
MAX_CYCLE_SPEED_KMH = 30.0  # Maximum allowed speed

# Station and transfer buffers
STATION_WAIT_TIME_MINUTES = 5.0  # Time to park bike, enter station, wait for train
EXIT_STATION_TIME_MINUTES = 2.0  # Time to exit station and get to bike
LINE_CHANGE_TIME_MINUTES = 5.0  # Buffer time when changing tube lines
SAME_PLATFORM_CHANGE_MINUTES = 2.0  # Reduced buffer for same platform changes

# Station access and waiting times
STATION_ACCESS_TIME_MINUTES = 2.0  # Time to enter/exit station (walking to/from platform)
TRAIN_WAITING_TIME_MINUTES = 5.0  # Average time waiting for train on platform

# Route preferences
PREFER_FEWER_CHANGES = True  # Prefer routes with fewer mode/line changes
MODE_CHANGE_PENALTY_MINUTES = 2.0  # Additional penalty for each mode change

# Display settings
SHOW_WAIT_TIMES = True  # Show wait times in journey breakdown
SHOW_PLATFORM_INFO = False  # Show platform/line details (if available)
USE_EMOJI_OUTPUT = True  # Use emojis in terminal output


def calculate_adjusted_edge_weight(
    base_duration: float,
    transport_mode: str,
    is_mode_change: bool = False,
    is_line_change: bool = False,
    is_same_platform: bool = False,
    custom_cycle_speed: float | None = None,
) -> float:
    """
    Calculate adjusted edge weight with configurable buffers.

    Args:
        base_duration: Base travel time in minutes
        transport_mode: 'bike' or 'tube'
        is_mode_change: True if changing from bike to tube or vice versa
        is_line_change: True if changing between tube lines
        is_same_platform: True if line change is on same platform
        custom_cycle_speed: Override default cycle speed (km/h)

    Returns:
        Adjusted duration in minutes including buffers
    """
    adjusted_duration = base_duration

    # Apply custom cycle speed if provided
    if transport_mode == "bike" and custom_cycle_speed is not None:
        # Recalculate duration based on custom speed
        # Note: This requires distance information
        speed_ratio = DEFAULT_CYCLE_SPEED_KMH / custom_cycle_speed
        adjusted_duration = base_duration * speed_ratio

    # Add buffers for mode changes
    if is_mode_change:
        if transport_mode == "tube":
            # Changing from bike to tube - need to park and enter station
            adjusted_duration += STATION_WAIT_TIME_MINUTES
        else:
            # Changing from tube to bike - need to exit station
            adjusted_duration += EXIT_STATION_TIME_MINUTES

        # Add mode change penalty if configured
        if PREFER_FEWER_CHANGES:
            adjusted_duration += MODE_CHANGE_PENALTY_MINUTES

    # Add buffers for line changes
    if is_line_change:
        if is_same_platform:
            adjusted_duration += SAME_PLATFORM_CHANGE_MINUTES
        else:
            adjusted_duration += LINE_CHANGE_TIME_MINUTES

        # Add line change penalty if configured
        if PREFER_FEWER_CHANGES:
            adjusted_duration += MODE_CHANGE_PENALTY_MINUTES * 0.5

    return adjusted_duration


def apply_journey_buffers(path_segments: list) -> list:
    """
    Apply buffers to a complete journey path.

    Args:
        path_segments: List of journey segments with format:
            [(station1, station2, edge_data), ...]

    Returns:
        Updated segments with adjusted durations and buffer information
    """
    adjusted_segments = []
    previous_mode = None
    previous_line = None

    for _i, (station1, station2, edge_data) in enumerate(path_segments):
        current_mode = edge_data.get("transport_mode", "unknown")
        current_line = edge_data.get("line")
        base_duration = edge_data.get("duration_minutes", 0)

        # Check for mode change
        is_mode_change = previous_mode is not None and previous_mode != current_mode

        # Check for line change (within tube network)
        is_line_change = (
            current_mode == "tube" and previous_mode == "tube" and previous_line != current_line
        )

        # Calculate adjusted duration
        adjusted_duration = calculate_adjusted_edge_weight(
            base_duration, current_mode, is_mode_change, is_line_change
        )

        # Create adjusted segment
        adjusted_edge_data = edge_data.copy()
        adjusted_edge_data["adjusted_duration_minutes"] = adjusted_duration
        adjusted_edge_data["base_duration_minutes"] = base_duration
        adjusted_edge_data["is_mode_change"] = is_mode_change
        adjusted_edge_data["is_line_change"] = is_line_change

        # Add buffer breakdown if applicable
        if is_mode_change or is_line_change:
            buffers = []
            if is_mode_change:
                if current_mode == "tube":
                    buffers.append(("Station entry", STATION_WAIT_TIME_MINUTES))
                else:
                    buffers.append(("Station exit", EXIT_STATION_TIME_MINUTES))
            if is_line_change:
                buffers.append(("Line change", LINE_CHANGE_TIME_MINUTES))
            adjusted_edge_data["buffers"] = buffers

        adjusted_segments.append((station1, station2, adjusted_edge_data))

        # Update previous mode/line for next iteration
        previous_mode = current_mode
        previous_line = current_line

    return adjusted_segments


def format_duration(minutes: float) -> str:
    """Format duration in minutes to human-readable string."""
    if minutes < 1:
        return f"{int(minutes * 60)} seconds"
    elif minutes < 60:
        return f"{minutes:.1f} minutes"
    else:
        hours = int(minutes // 60)
        mins = int(minutes % 60)
        if mins == 0:
            return f"{hours} hour{'s' if hours > 1 else ''}"
        return f"{hours}h {mins}m"


def get_transport_emoji(mode: str) -> str:
    """Get emoji for transport mode."""
    if not USE_EMOJI_OUTPUT:
        return ""

    emoji_map = {
        "bike": "🚴",
        "tube": "🚇",
        "wait": "⏱️",
        "walk": "🚶",
        "total": "📍",
    }
    return emoji_map.get(mode, "❓")


def validate_cycle_speed(speed_kmh: float) -> float:
    """Validate and clamp cycle speed to reasonable bounds."""
    if speed_kmh < MIN_CYCLE_SPEED_KMH:
        print(f"⚠️  Cycle speed {speed_kmh} km/h too low, using minimum {MIN_CYCLE_SPEED_KMH} km/h")
        return MIN_CYCLE_SPEED_KMH
    elif speed_kmh > MAX_CYCLE_SPEED_KMH:
        print(f"⚠️  Cycle speed {speed_kmh} km/h too high, using maximum {MAX_CYCLE_SPEED_KMH} km/h")
        return MAX_CYCLE_SPEED_KMH
    return speed_kmh
