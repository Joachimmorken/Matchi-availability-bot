#!/usr/bin/env python3
"""Tennis Court Availability Monitor for Matchi.se facilities."""

import argparse
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
    """Send a visual alert popup using osascript."""
    try:
        # Use display alert instead of notification - more reliable and no permissions needed
        script = f"""
        display alert "{title}" message "{message}" giving up after 5
        """
        subprocess.run(["osascript", "-e", script], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Failed to send alert: {e}")
    except Exception as e:
        print(f"Error sending alert: {e}")


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
    # Determine court type and icon
    if "grusbane" in court_name.lower():
        icon = "🟡"
    elif "hardcourt" in court_name.lower():
        icon = "🔵"
    else:
        icon = "⚪"

    # Apply status styling
    if is_new:
        return "bold bright_green", f"🆕{icon}"
    elif is_removed:
        return "strike dim white", f"❌{icon}"
    else:
        return "white", icon


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

            # Get changes for this facility and date (only if we have previous data)
            if previous_slots:
                new_courts, removed_courts = get_slot_changes(
                    all_slots, previous_slots, facility_name, date
                )
            else:
                new_courts, removed_courts = set(), set()

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
    # If previous_slots is empty (first run), don't consider it a change
    if not previous_slots:
        return False
    return current_slots != previous_slots


def get_changes_summary(current_slots, previous_slots):
    """Get a summary of what changed."""
    changes = []
    dates = get_date_range(2)

    # Don't generate changes if previous_slots is empty (first run)
    if not previous_slots:
        return changes

    for facility_name in facilities.keys():
        facility_display = facility_name.capitalize()
        for date in dates:
            current = current_slots.get(facility_name, {}).get(date, {})
            previous = previous_slots.get(facility_name, {}).get(date, {})

            if current != previous:
                date_str = format_date_header(date)

                # Count actual new courts
                current_courts = set()
                previous_courts = set()

                for time_slot, courts in current.items():
                    for court in courts:
                        current_courts.add((time_slot, court))

                for time_slot, courts in previous.items():
                    for court in courts:
                        previous_courts.add((time_slot, court))

                new_courts = current_courts - previous_courts
                removed_courts = previous_courts - current_courts

                if new_courts:
                    changes.append(
                        f"New courts available at {facility_display} on {date_str}"
                    )
                if removed_courts:
                    changes.append(f"Courts taken at {facility_display} on {date_str}")

    return changes


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
    legend_table.add_row(
        "🔔 Alerts", "[blue]Visual popups (auto-close after 5s)[/blue]"
    )

    console.print(legend_table)
    console.print("Press Ctrl+C to stop monitoring\n", style="dim")


def test_notifications():
    """Test the alert system to ensure it's working."""
    console.print("🔔 Testing alert system...\n", style="bold blue")

    console.print(
        "💡 This system uses visual popup alerts instead of notifications.",
        style="blue",
    )
    console.print(
        "Alerts appear as dialogs and automatically disappear after 5 seconds.",
        style="blue",
    )
    console.print("No special permissions required!\n", style="green")

    # Ask for confirmation before proceeding
    console.print(
        "Press Enter to continue with alert test, or Ctrl+C to exit...",
        style="dim",
    )
    try:
        input()
    except KeyboardInterrupt:
        console.print("\n❌ Test cancelled.", style="yellow")
        return

    test_messages = [
        (
            "🎾 Tennis Alert Test",
            "If you see this popup, alerts are working perfectly!",
        ),
        (
            "🏟️ System Check",
            "Tennis court monitor will show popups when courts become available.",
        ),
        ("✅ Test Complete", "Alert system is functioning correctly."),
    ]

    for i, (title, message) in enumerate(test_messages, 1):
        console.print(f"Sending test alert {i}/3...", style="dim")
        send_notification(title, message)

        if i < len(test_messages):
            console.print("Waiting 3 seconds before next test...", style="dim")
            time.sleep(3)

    console.print("\n🔔 Alert test complete!", style="bold green")
    console.print(
        "✅ If you saw 3 popup dialogs: System is working correctly!",
        style="bold green",
    )
    console.print(
        "❌ If you didn't see any popups: Check if Terminal has permission to control your computer",
        style="yellow",
    )
    console.print(
        "💡 Alerts appear as popup dialogs and disappear automatically after 5 seconds",
        style="dim blue",
    )


def run_monitor():
    """Run the main court availability monitoring loop."""
    # Initialize previous state
    previous_slots = {}

    show_legend()

    while True:  # Infinite loop to keep the script running
        try:
            current_slots = collect_all_slots()

            # Check for changes (only after first run)
            changes_detected = has_changes(current_slots, previous_slots)
            if changes_detected:
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
            elif previous_slots:  # Only show "no changes" if this isn't the first run
                console.print(
                    "\n✓ No changes detected. Courts status unchanged.",
                    style="dim green",
                )

            # Always display current state (with highlighting if there were changes)
            display_slots_table(
                current_slots,
                previous_slots if changes_detected else {},
            )

            # Update previous state
            previous_slots = current_slots.copy()

            next_check_time = (
                datetime.datetime.now() + datetime.timedelta(minutes=5)
            ).strftime("%H:%M:%S")
            console.print(
                f"\n⏰ Next check in 5 minutes... (at {next_check_time})",
                style="dim blue",
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


def main():
    """Main entry point with command-line argument parsing."""
    parser = argparse.ArgumentParser(
        description="🎾 Tennis Court Availability Monitor for Matchi.se",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                     Start monitoring (default)
  %(prog)s monitor             Start monitoring
  %(prog)s test-notifications  Test alert system
  %(prog)s --help              Show this help message

For more information, visit: https://github.com/your-username/tennis-bot
        """.strip(),
    )

    subparsers = parser.add_subparsers(
        dest="command", help="Available commands", metavar="COMMAND"
    )

    # Monitor command (default)
    monitor_parser = subparsers.add_parser(
        "monitor",
        help="Start monitoring tennis court availability (default)",
        description="Monitor tennis courts and send notifications when slots become available",
    )

    # Test notifications command
    test_parser = subparsers.add_parser(
        "test-notifications",
        help="Test the alert system",
        description="Send test popup alerts to verify the system is working",
    )

    args = parser.parse_args()

    # Default to monitor if no command specified
    if args.command is None:
        args.command = "monitor"

    # Route to appropriate function
    if args.command == "monitor":
        run_monitor()
    elif args.command == "test-notifications":
        test_notifications()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
