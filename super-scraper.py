import requests
from bs4 import BeautifulSoup
from icalendar import Calendar, Event
from datetime import datetime, timedelta, date
import pytz 
from html import unescape

def clean(text):
    if isinstance(text, str):
        return unescape(text).strip().replace('\\','').replace('â', '-').replace('’', "'").replace("Ã¢ÂÂ", "-").replace("â", "'").replace("\\,", ",").replace("–","-").replace("Ã©", "é")
    else:
        return text

today = date.today()

# Help stop calendar abuse. Only pull events within a reasonable time frame.
start_date = (today - timedelta(days=365)).strftime("%m/%d/%Y")
end_date = (today + timedelta(days=365)).strftime("%m/%d/%Y")


print("Starting from: " + start_date)
print("Ending at: " + end_date)

url = "https://calendar.wsplibrary.ca/default/List?StartDate=" + start_date + "&EndDate=" + end_date
latest_cal_url = "https://github.com/the404devs/wspl-calendar-scraper/releases/latest/download/WSPL_Events.ics"

print("Target URL: " + url)

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
        summary = clean(component.get('summary'))
        event_date = clean(component.get('dtstart').dt)
        event_link = clean(component.get('url'))
        latest_event_summaries_dates.add((summary, event_date, event_link))

request_counter = 1
calendars = []
skipped_events = []
bad_events = []
for item in calendar_items:

        something_has_gone_horribly_wrong = False
        super_happy_fun_no_date_url_event_counter = 0

        meta_title = item.find(class_='meta-title')
        event_summary = clean(meta_title.text)

        meta_url = meta_title.get('href')
        event_link = "https://calendar.wsplibrary.ca" + meta_url

        try:
            meta_date = meta_url[16:32].replace('-', '')
            event_date = datetime.strptime(meta_date, '%Y%m%d%H%M')
            # Convert event_date to UTC
            local = pytz.timezone("America/Toronto")
            local_dt = local.localize(event_date, is_dst=None)
            event_date = local_dt.astimezone(pytz.utc)
        except ValueError:
            # Events from Oct. 2024 onwards don't have the date in the url, which annoys me greatly.
            # Now we must pull the event's page and pull the date from there.
            # Hopefully this doesn't ddos the calendar.
            print("--------------------")
            print("Could not find date in URL. Reluctantly pulling event page.")
            print(event_link)
            request_counter += 1
            super_happy_fun_no_date_url_event_counter +=1
            event_page = requests.get(event_link)
            soup2 = BeautifulSoup(clean(event_page.text), 'html.parser')
            date_div = soup2.find(class_='icrt-calendarContentSideContent') # the js i inject into the event page gives this div an id. that won't help me here though

            if (date_div != None):
                pp = date_div.findAll('p')
                this_should_be_year_month_day = clean(pp[0].text)
                this_should_be_start_and_end_time = clean(pp[1].text)

                this_should_be_start_time = this_should_be_start_and_end_time.split(" - ")[0]
                # print("yyyymmdd: " + this_should_be_year_month_day)
                # print("among us hh:mm: " + this_should_be_start_time)

                this_should_be_the_full_date_time_in_a_human_readable_string = this_should_be_year_month_day + ", " + this_should_be_start_time

                # print("|"+this_should_be_the_full_date_time_in_a_human_readable_string+"|")
                event_date = datetime.strptime(this_should_be_the_full_date_time_in_a_human_readable_string, '%B %d, %Y, %I:%M %p')
                # Convert event_date to UTC
                local = pytz.timezone("America/Toronto")
                local_dt = local.localize(event_date, is_dst=None)
                event_date = local_dt.astimezone(pytz.utc)
            else:
                something_has_gone_horribly_wrong = True
                print("WARN: Could not find any date on this event page.")
                print("Something has gone horribly wrong, and there's a 95% chance the problem lies in the calendar's backend where I can't fix it.")
                print("BAD EVENT LINK: " + event_link)
                bad_events.append(event_link)





        if not something_has_gone_horribly_wrong:
            if (event_summary, event_date, event_link) in latest_event_summaries_dates:
                # print(f"Skipping event: {event_summary}")
                skipped_events.append((event_summary, event_date, event_link))
            else:
                print(f"Pulling event: |{event_summary}|{event_date}|")
                request_counter += 1
                ical_link = event_link.replace('/Detail/', '/Calendar/')
                print(ical_link)
                calendar_response = requests.get(ical_link)
                calendar = Calendar.from_ical(clean(calendar_response.text))
                event = calendar.walk()[1]
                event['url'] = event_link
                calendars.append(calendar)

combined_calendar = Calendar()

print("--------------------")
print(f"{len(skipped_events)} events skipped.")
print(f"{request_counter} request(s) sent to calendar.wsplibrary.ca")
print('Generating iCal file...')

fresh_totals = 0
skipped_totals = 0

# Add skipped events from the latest release to the combined calendar
for summary, event_date, event_link in skipped_events:
    for component in latest_cal.walk():
        if component.name == 'VEVENT':
            if component.get('summary') == summary and component.get('dtstart').dt == event_date and component.get('url') == event_link:
                event = Event()
                for property_name, property_value in component.items():
                    event[property_name] = clean(property_value)
                skipped_totals += 1
                combined_calendar.add_component(event)
                break

# Add in the freshly-pulled events from the calendar
for calendar in calendars:
    for component in calendar.walk():
        if component.name == 'VEVENT' and component not in combined_calendar.subcomponents:
            event = Event()
            for property_name, property_value in component.items():
                event[property_name] = clean(property_value)
            fresh_totals += 1
            combined_calendar.add_component(event)

print(f"{fresh_totals} fresh events, {skipped_totals} skipped events.")
with open('WSPL_Events.ics', 'wb') as f:
    f.write(combined_calendar.to_ical())
print('Complete!')

# Print the number of events in the combined calendar
num_events_combined = sum(1 for _ in combined_calendar.walk() if _.name == 'VEVENT')
print(f'Number of events in combined_calendar: {num_events_combined}')

print(f'Number of events that couldn\'t be pulled: {len(bad_events)}')


if (len(bad_events) > 0):
    with open("seemingly-broken-events.txt", "w") as f:
        f.write("Broken Event Page Report at " + datetime.today().strftime('%Y-%m-%d %H:%M:%S') + "UTC\n")
        f.write("The following event pages are probably broken (that's bad):\n")
        f.write("Most likely causes are: event url without date/time, causing events with the same name to have the same url:\n\n")
        for url in bad_events:
            f.write(url + "\n")
else:
    with open("seemingly-broken-events.txt", "w") as f:
        f.write("Broken Event Page Report at " + datetime.today().strftime('%Y-%m-%d %H:%M:%S') + "UTC\n")
        f.write("All is well. No problems, this time.")
