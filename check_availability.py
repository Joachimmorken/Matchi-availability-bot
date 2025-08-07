#!/usr/bin/env python3
"""Tennis Court Availability Monitor for Matchi.se facilities."""

import datetime
import subprocess
import time
from collections import defaultdict

import requests
from bs4 import BeautifulSoup
from rich.console import Console
from rich.table import Table
from rich.text import Text
from rich import box

from facilities import facilities

# Initialize rich console
console = Console()


def send_notification(title, message):
    """Send a native macOS notification using osascript."""
    try:
        script = f"""
        display notification "{message}" with title "{title}"
        """
        subprocess.run(["osascript", "-e", script], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Failed to send notification: {e}")
    except Exception as e:
        print(f"Error sending notification: {e}")


def fetch_available_slots(facility_name, target_date):
    """Fetch available slots for a specific facility and date."""
    facility_id = facilities[facility_name.lower()]
    date_str = target_date.strftime("%Y-%m-%d")
    url = f"https://www.matchi.se/book/schedule?wl=&facilityId={facility_id}&date={date_str}&sport=1"

    # Fetch the content from the URL
    response = requests.get(url)
    response.raise_for_status()  # Raise an exception for HTTP errors

    # Parse the content using BeautifulSoup
    soup = BeautifulSoup(response.text, "html.parser")

    # Search for all 'td' elements with class "slot free"
    available_slots = soup.find_all("td", class_="slot free")

    # Create a dictionary to group courts by time slots
    time_slot_dict = {}

    for slot in available_slots:
        # Split the title to extract court and time information
        parts = slot["title"].split("<br>")
        court = parts[1]
        time = parts[2]

        # Add the court to the corresponding time slot in the dictionary
        if time in time_slot_dict:
            time_slot_dict[time].append(court)
        else:
            time_slot_dict[time] = [court]

    # Return the time slot dictionary (empty if no slots available)
    return time_slot_dict


def get_date_range(days_ahead=2):
    """Get a list of dates from today to days_ahead from today."""
    today = datetime.date.today()
    return [today + datetime.timedelta(days=i) for i in range(days_ahead + 1)]


def format_date_header(date):
    """Format date for display headers."""
    if date == datetime.date.today():
        return f"Today ({date.strftime('%Y-%m-%d')})"
    elif date == datetime.date.today() + datetime.timedelta(days=1):
        return f"Tomorrow ({date.strftime('%Y-%m-%d')})"
    else:
        return f"{date.strftime('%A, %Y-%m-%d')}"


def get_court_style(court_name, is_new=False, is_removed=False):
    """Get styling for court based on type and status."""
    # Determine court type and base color
    if "grusbane" in court_name.lower():
        base_color = "yellow"  # Clay courts in yellow
        icon = "🟡"
    elif "hardcourt" in court_name.lower():
        base_color = "cyan"  # Hard courts in cyan
        icon = "🔵"
    else:
        base_color = "white"  # Unknown courts in white
        icon = "⚪"

    # Apply status styling
    if is_new:
        return f"bold bright_green", f"🆕{icon}"
    elif is_removed:
        return f"strike dim {base_color}", f"❌{icon}"
    else:
        return base_color, icon


def collect_all_slots():
    """Collect slots for all facilities and dates."""
    all_slots = {}
    dates = get_date_range(2)  # Today + 2 days

    console.print("\n🎾 Checking tennis court availability...\n", style="bold blue")

    for facility_name in facilities.keys():
        facility_display_name = facility_name.capitalize()
        all_slots[facility_name] = {}

        for date in dates:
            try:
                slots = fetch_available_slots(facility_name, date)
                all_slots[facility_name][date] = slots
                console.print(
                    f"✓ Checked {facility_display_name} for {format_date_header(date)}",
                    style="green",
                )
            except Exception as e:
                console.print(
                    f"✗ Error checking {facility_display_name} for {format_date_header(date)}: {e}",
                    style="red",
                )
                all_slots[facility_name][date] = {}

    return all_slots


def get_slot_changes(current_slots, previous_slots, facility_name, date):
    """Get new and removed courts for a specific facility and date."""
    current = set()
    previous = set()

    current_day_slots = current_slots.get(facility_name, {}).get(date, {})
    previous_day_slots = previous_slots.get(facility_name, {}).get(date, {})

    # Flatten court lists for comparison
    for time_slot, courts in current_day_slots.items():
        for court in courts:
            current.add((time_slot, court))

    for time_slot, courts in previous_day_slots.items():
        for court in courts:
            previous.add((time_slot, court))

    new_courts = current - previous
    removed_courts = previous - current

    return new_courts, removed_courts


def display_slots_table(all_slots, previous_slots=None):
    """Display slots in a beautiful colored tabular format with highlighting."""
    dates = get_date_range(2)

    if previous_slots is None:
        previous_slots = {}

    for facility_name, facility_data in all_slots.items():
        facility_display_name = facility_name.capitalize()

        # Create facility header
        console.print(
            f"\n🏟️  {facility_display_name} Tennis Courts", style="bold magenta"
        )
        console.print("=" * 60, style="magenta")

        for date in dates:
            date_header = format_date_header(date)
            slots = facility_data.get(date, {})

            # Get changes for this facility and date
            new_courts, removed_courts = get_slot_changes(
                all_slots, previous_slots, facility_name, date
            )

            # Create table for this date
            table = Table(
                title=f"📅 {date_header}",
                box=box.ROUNDED,
                title_style="bold blue",
                show_header=True,
                header_style="bold white",
            )
            table.add_column("Time Slot", style="bold cyan", width=15)
            table.add_column("Available Courts", style="white", min_width=40)

            if not slots:
                table.add_row("", "[dim]No available slots[/dim]")
            else:
                # Add rows for each time slot
                for time_slot in sorted(slots.keys()):
                    courts = slots[time_slot]

                    # Style each court individually
                    styled_courts = []
                    for court in courts:
                        is_new = (time_slot, court) in new_courts
                        is_removed = (time_slot, court) in removed_courts

                        style, icon = get_court_style(court, is_new, is_removed)
                        styled_court = Text(f"{icon} {court}", style=style)
                        styled_courts.append(styled_court)

                    # Combine styled courts
                    if styled_courts:
                        courts_display = Text()
                        for i, styled_court in enumerate(styled_courts):
                            if i > 0:
                                courts_display.append(", ")
                            courts_display.append(styled_court)
                        table.add_row(time_slot, courts_display)

            console.print(table)
            console.print()  # Add spacing between tables


def has_changes(current_slots, previous_slots):
    """Check if there are any changes between current and previous slots."""
    return current_slots != previous_slots


def get_changes_summary(current_slots, previous_slots):
    """Get a summary of what changed."""
    changes = []
    dates = get_date_range(2)

    for facility_name in facilities.keys():
        facility_display = facility_name.capitalize()
        for date in dates:
            current = current_slots.get(facility_name, {}).get(date, {})
            previous = previous_slots.get(facility_name, {}).get(date, {})

            if current != previous:
                date_str = format_date_header(date)
                if current and not previous:
                    changes.append(f"New slots at {facility_display} on {date_str}")
                elif not current and previous:
                    changes.append(
                        f"All slots taken at {facility_display} on {date_str}"
                    )
                elif current != previous:
                    changes.append(f"Slot changes at {facility_display} on {date_str}")

    return changes


# Initialize previous state
previous_slots = {}


def show_legend():
    """Display the legend for court types and status indicators."""
    console.print("\n🎾 Tennis Court Availability Monitor", style="bold blue")
    console.print(
        "Monitoring both Frogner and Voldsløkka for the next 3 days", style="blue"
    )

    legend_table = Table(
        title="Legend", box=box.SIMPLE, show_header=False, title_style="bold yellow"
    )
    legend_table.add_column("Symbol", style="bold")
    legend_table.add_column("Meaning")

    legend_table.add_row("🟡 Grusbane", "[yellow]Clay courts[/yellow]")
    legend_table.add_row("🔵 Hardcourt", "[cyan]Hard courts[/cyan]")
    legend_table.add_row(
        "🆕 New", "[bold bright_green]Newly available[/bold bright_green]"
    )
    legend_table.add_row("❌ Removed", "[strike dim]No longer available[/strike dim]")

    console.print(legend_table)
    console.print("Press Ctrl+C to stop monitoring\n", style="dim")


show_legend()

while True:  # Infinite loop to keep the script running
    try:
        current_slots = collect_all_slots()

        # Check for changes
        if has_changes(current_slots, previous_slots):
            changes = get_changes_summary(current_slots, previous_slots)

            # Send notification
            if changes:
                summary = "; ".join(
                    changes[:3]
                )  # Limit to first 3 changes for notification
                if len(changes) > 3:
                    summary += f" and {len(changes) - 3} more..."

                send_notification(
                    title="🎾 Tennis Courts Updated!",
                    message=summary,
                )

            console.print("\n🔔 Changes detected!", style="bold green")
            if changes:
                for change in changes:
                    console.print(f"   • {change}", style="green")
        else:
            console.print(
                "\n✓ No changes detected. Courts status unchanged.", style="dim green"
            )

        # Always display current state (with highlighting if there were changes)
        display_slots_table(
            current_slots,
            previous_slots if has_changes(current_slots, previous_slots) else None,
        )

        # Update previous state
        previous_slots = current_slots.copy()

        next_check_time = (
            datetime.datetime.now() + datetime.timedelta(minutes=5)
        ).strftime("%H:%M:%S")
        console.print(
            f"\n⏰ Next check in 5 minutes... (at {next_check_time})", style="dim blue"
        )
        time.sleep(300)  # Sleep for 5 minutes

    except KeyboardInterrupt:
        console.print(
            "\n\n👋 Monitoring stopped. Have a great game!", style="bold blue"
        )
        break
    except Exception as e:
        console.print(f"\n❌ Error occurred: {e}", style="red")
        console.print("Retrying in 1 minute...", style="yellow")
        time.sleep(60)
