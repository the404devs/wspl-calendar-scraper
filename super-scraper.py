import requests
from bs4 import BeautifulSoup
from icalendar import Calendar

url = "https://calendar.wsplibrary.ca/default/List?StartDate=01/01/2021&EndDate=12/31/2030"

print('Fetching calendar data...')
response = requests.get(url)

print('Calendar data received.')

fixed = response.text.replace('&amp;', '&').replace("’","'")
soup = BeautifulSoup(response.text, 'html.parser')

calendar_items = soup.find_all(class_='icrt-calendarListItem')
print(str(len(calendar_items)) + " events to parse.")

calendars = []
for item in calendar_items:
        meta_title = item.find(class_='meta-title')
        #print(meta_title.text)

        if meta_title is None:
            continue
        link = "https://calendar.wsplibrary.ca" + meta_title.get('href').replace('/Detail/', '/Calendar/')
        calendar_response = requests.get(link)
        calendar = Calendar.from_ical(calendar_response.text)
        calendars.append(calendar)
        
combined_calendar = Calendar()
print('Generating iCal file...')
for calendar in calendars:
    for component in calendar.walk():
        combined_calendar.add_component(component)
        
with open('WSPL_Events.ics', 'wb') as f:
    f.write(combined_calendar.to_ical())
print('Complete!')
