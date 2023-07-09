import requests
from bs4 import BeautifulSoup
from icalendar import Calendar, Event
from datetime import datetime
import pytz 
from html import unescape

def clean(text):
    return unescape(text).strip().replace('\\','').replace('â', '-').replace('’', "'").replace("Ã¢ÂÂ", "-").replace("â", "'")

url = "https://calendar.wsplibrary.ca/default/List?StartDate=01/01/2021&EndDate=12/31/2030"
latest_cal_url = "https://github.com/the404devs/wspl-calendar-scraper/releases/latest/download/WSPL_Events.ics"

print('Fetching calendar data...')
response = requests.get(url)
print('Calendar data received.')

soup = BeautifulSoup(clean(response.text), 'html.parser')

calendar_items = soup.find_all(class_='icrt-calendarListItem')
print(str(len(calendar_items)) + " events to parse.")

# Fetch the latest calendar from GitHub
print("Pulling latest release from GitHub...")
latest_cal_response = requests.get(latest_cal_url)
latest_cal = Calendar.from_ical(clean(latest_cal_response.text))
print("Latest release retrieved.")

# Store event summaries and dates from the latest calendar in a set
latest_event_summaries_dates = set()
for component in latest_cal.walk():
    if component.name == 'VEVENT':
        summary = component.get('summary')
        event_date = component.get('dtstart').dt
        # print(str(event_date))
        latest_event_summaries_dates.add((summary, event_date))

request_counter = 1
calendars = []
skipped_events = []
for item in calendar_items:
        meta_title = item.find(class_='meta-title')
        meta_date = meta_title.get('href')[16:32].replace('-', '')
        event_summary = meta_title.text
        event_date = datetime.strptime(meta_date, '%Y%m%d%H%M')

        # Convert event_date to UTC
        local = pytz.timezone("America/Toronto")
        local_dt = local.localize(event_date, is_dst=None)
        event_date = local_dt.astimezone(pytz.utc)

        if (event_summary, event_date) in latest_event_summaries_dates:
            # print(f"Skipping event: {event_summary}")
            skipped_events.append((event_summary, event_date))
        else:
            print(f"Pulling event: {event_summary}")
            request_counter += 1
            link = "https://calendar.wsplibrary.ca" + meta_title.get('href').replace('/Detail/', '/Calendar/')
            calendar_response = requests.get(link)
            calendar = Calendar.from_ical(clean(calendar_response.text))
            calendars.append(calendar)

combined_calendar = Calendar()

print(f"{len(skipped_events)} events skipped.")
print(f"{request_counter} request(s) sent to calendar.wsplibrary.ca")
print('Generating iCal file...')

fresh_totals = 0
skipped_totals = 0

# Add skipped events from the latest release to the combined calendar
for summary, event_date in skipped_events:
    for component in latest_cal.walk():
        if component.name == 'VEVENT':
            if component.get('summary') == summary and component.get('dtstart').dt == event_date:
                event = Event()
                for property_name, property_value in component.items():
                    event[property_name] = property_value
                skipped_totals += 1
                combined_calendar.add_component(event)
                break

for calendar in calendars:
    for component in calendar.walk():
        if component.name == 'VEVENT' and component not in combined_calendar.subcomponents:
            fresh_totals += 1
            combined_calendar.add_component(component)

print(f"{fresh_totals} fresh events, {skipped_totals} skipped events.")
with open('WSPL_Events.ics', 'wb') as f:
    f.write(combined_calendar.to_ical())
print('Complete!')

# Print the number of events in the combined calendar
num_events_combined = sum(1 for _ in combined_calendar.walk() if _.name == 'VEVENT')
print(f'Number of events in combined_calendar: {num_events_combined}')
