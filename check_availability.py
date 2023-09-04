import datetime  # Import the datetime module
import time

from facilities import facilities

import requests
from bs4 import BeautifulSoup
from plyer import notification


def fetch_available_slots():
    # Get today's date in the format YYYY-MM-DD
    todays_date = datetime.date.today().strftime('%Y-%m-%d')
    tomorrows_date = (datetime.date.today() +
                      datetime.timedelta(days=1)).strftime('%Y-%m-%d')

    facility_to_check = facilities.voldslokka
    url = f"https://www.matchi.se/book/schedule?wl=&facilityId={facility_to_check}&date={todays_date}&sport=1"

    # Fetch the content from the URL
    response = requests.get(url)
    response.raise_for_status()  # Raise an exception for HTTP errors

    # Parse the content using BeautifulSoup
    soup = BeautifulSoup(response.text, 'html.parser')

    # Search for all 'td' elements with class "slot free"
    available_slots = soup.find_all('td', class_='slot free')

    # Create a dictionary to group courts by time slots
    time_slot_dict = {}

    for slot in available_slots:
        # Split the title to extract court and time information
        parts = slot['title'].split('<br>')
        court = parts[1]
        time = parts[2]

        # Add the court to the corresponding time slot in the dictionary
        if time in time_slot_dict:
            time_slot_dict[time].append(court)
        else:
            time_slot_dict[time] = [court]

    # If there are no available slots, print a message and exit
    if not time_slot_dict:
        print("No available slots")
        return {}

    return time_slot_dict


# Initialize an empty dictionary for the previous state
previous_slots = {}

while True:  # Infinite loop to keep the script running
    current_slots = fetch_available_slots()

    # Compare current_slots with previous_slots to detect changes
    if current_slots != previous_slots:
        notification.notify(
            title='Available Slots Updated!',
            message='Detected changes in available slots. Check the console for details.',
            timeout=10  # Notification stays for 10 seconds
        )
        print("Detected changes in available slots!")

        # Print the results
        for timestamp, courts in sorted(current_slots.items()):
            courts_str = ', '.join(courts)
            print(f"{timestamp}: {courts_str}")
            print('-' * 40)  # Add a separator for clarity

        # Update the previous state
        previous_slots = current_slots

    # Sleep for 5 minutes (300 seconds) before the next iteration
    time.sleep(300)
