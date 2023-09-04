
# Matchi Availability Bot

## Overview

The Matchi Availability Bot is a Python application designed to check and notify users about available slots for facilities listed on the Matchi booking website (`https://www.matchi.se/book/schedule`). It uses web scraping techniques to fetch the available time slots for a specified facility and date.

## Features

- Fetches available slots for a given facility and date from Matchi's website.
- Sends desktop notifications for available slots.

## Pre-requisites

- Python 3.x
- Poetry (for dependency management)

## Installation

### Clone the Repository

First, clone the repository to your local machine:

```bash
git clone <repository_url>
```

### Install Dependencies

Navigate to the project folder and install the required dependencies using Poetry:

```bash
cd Matchi-availability-bot
poetry install
```

## Usage

To run the script, use the following command:

```bash
poetry run python check_availability.py
```

## License

This project is licensed under the terms of the license specified in the [LICENSE](LICENSE) file.
