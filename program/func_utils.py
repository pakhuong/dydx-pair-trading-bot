from datetime import datetime, timedelta


# Format number
def format_number(curr_num, match_num):
    """
      Give current number an example of number with decimals desired
      Function will return the correctly formatted string
    """

    curr_num_string = f"{curr_num}"
    match_num_string = f"{match_num}"

    # Round to match decimals
    if "." in match_num_string:
        match_decimals = len(match_num_string.split(".")[1])
        curr_num_string = f"{curr_num:.{match_decimals}f}"
        curr_num_string = curr_num_string[:]
        return curr_num_string

    # Round to nearest integer
    if match_num_string == "1":
        curr_num_string = f"{int(curr_num)}"
        return curr_num_string

    # Round to nearest ten
    if match_num_string == "10":
        curr_num_string = f"{int(curr_num)}"
        curr_num_string = curr_num_string[:-1] + "0"
        return curr_num_string

    return f"{int(curr_num)}"


# Format time
def format_time(timestamp):
    return timestamp.replace(microsecond=0).isoformat()


# Get ISO Times
def get_ISO_times():

    # Get timestamps
    date_start_0 = datetime.utcnow()
    date_start_1 = date_start_0 - timedelta(days=100)
    date_start_2 = date_start_1 - timedelta(days=100)
    date_start_3 = date_start_2 - timedelta(days=100)
    date_start_4 = date_start_3 - timedelta(days=100)

    # Format datetimes
    times_dict = {
        "range_1": {
            "from_iso": format_time(date_start_1),
            "to_iso": format_time(date_start_0),
        },
        "range_2": {
            "from_iso": format_time(date_start_2),
            "to_iso": format_time(date_start_1),
        },
        "range_3": {
            "from_iso": format_time(date_start_3),
            "to_iso": format_time(date_start_2),
        },
        "range_4": {
            "from_iso": format_time(date_start_4),
            "to_iso": format_time(date_start_3),
        },
    }

    # Return result
    return times_dict
