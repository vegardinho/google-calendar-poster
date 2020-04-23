from __future__ import print_function
from datetime import date,timedelta,datetime
from dateutil.relativedelta import relativedelta
import pickle
import os.path
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from ics import Calendar
import requests
from googleapiclient.errors import HttpError

MONTHS_FWD = 12
MONTHS_BACK = 2

def main():
    service = setup()
    new_events = get_events()
    old_events = get_old_events(service)

    for event in new_events:
        exists = check_existance(service, event, old_events)
        if exists != None:
            post_event(service, event, exists)

    for event in old_events:
        try:
            if "still_exists" not in event.keys() and event["source"]["title"] == "Eventor-arrangement":
                print("deleting event:")
                print(event)
                service.events().delete(calendarId='primary', eventId=event["id"]).execute()
        except:
            continue

# Check if event from downloaded ics-file already exists online.
def check_existance(service, new_event, old_events):
    service = service
    new_event = new_event

    for event in old_events:
        if event["id"] == new_event["id"]:
            event["still_exists"] = True

            for e in new_event:
                try:
                    if new_event[e] != event[e]:
                        print("Event has changed!")
                        return True
                except KeyError as e:
                    print("Tag does not exist:", e)

            print("Event has not changed")
            return None

    print("New event")
    print(new_event)
    return False

def setup():
    # If modifying these scopes, delete the file token.pickle.
    SCOPES = ['https://www.googleapis.com/auth/calendar']

    creds = None
    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                    'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    return build('calendar', 'v3', credentials=creds)


# Post event either by updating existing, or creating new event
def post_event(service, event, exists):
    exists = exists
    e = event
    service = service

    event_body = {
            'summary': e["summary"],
            'location': e["location"],
            'id': e["id"],
            'source': e["source"],
            'description': e["description"],
            'start': e["start"],
            'end': e["end"]
            }

    try:
        if exists == True:
            event = service.events().update(calendarId='primary', eventId=event_body["id"], body=event_body).execute()
        elif exists == False:
            event = service.events().insert(calendarId='primary', body=event_body).execute()
    except HttpError as err:
        print("ERROR:", err)

    #TODO: in except: remove from trash
    print('Event created: %s' % (event.get('htmlLink')))
    print(event.get('id'))


# Get .ics file from site (with events from now and three months forward), and make dictionary with relevant info for each event, and return list
# Id is changed to fit limitations in google calendar id pattern.
def get_events():

    today = date.today()
    start_date = today - relativedelta(months=MONTHS_BACK)
    end_date = today + relativedelta(months=MONTHS_FWD)

    url = 'https://eventor.orientering.no/Events/ExportICalendarEvents?startDate={}&endDate={}&organisations=5%2C19&classifications=International%2CChampionship%2CNational%2CRegional%2CLocal'.format(start_date, end_date)
    response = requests.get(url)
    response.encoding = 'utf-8'
    c = Calendar(response.text)
    # c = Calendar(open("/Users/vegardlandsverk/Downloads/Events.ics").read())

    eventorEv = list(c.timeline)
    events = []

    for event in eventorEv:
        summary = event.name.split(", ")

        time = get_time_format(event.begin, event.end)

        info = {
            'summary': '{} ({})'.format("".join(summary[:-1]), summary[-1]),
            "location": event.location,
            "source": {
                'title': 'Eventor-arrangement',
                'url': event.url
                },
            'id': event.uid.split("@")[0].lower().replace('_', ''),
            'description': 'Se <a href={}>Eventor-arrangementet</a> for mer informasjon'.format(event.url),
            "start": time[0],
            "end": time[1]
            }

        events.append(info)

    return events


def get_time_format(start_date, end_date):

    s_date = start_date.to('Europe/Oslo')
    e_date = end_date.to('Europe/Oslo')

    if (s_date.timetuple().tm_hour == s_date.timetuple().tm_hour == 0):
        start = {'date': s_date.format("YYYY-MM-DD")}
        end = {'date': e_date.format("YYYY-MM-DD")}
    else:
        start = {
            'dateTime': s_date.format("YYYY-MM-DDTHH:mm:ssZZ"), 
            'timeZone': 'Etc/UTC'
            }
        end = {
            'dateTime': e_date.format("YYYY-MM-DDTHH:mm:ssZZ"), 
            'timeZone': 'Etc/UTC'
            }
    return [start, end]


# Fetch list of all events from chosen Google calendar, and return list
def get_old_events(service):
    today = datetime.today()
    start = today - relativedelta(months=MONTHS_BACK)
    end = today + relativedelta(months=MONTHS_FWD)

    tmax = end.isoformat('T') + "Z"
    tmin = start.isoformat('T') + "Z"

    events = []
    page_token = None
    while True:
        evs = service.events().list(calendarId='primary', pageToken=page_token, timeMin=tmin,
                timeMax=tmax, showDeleted=False).execute()
        page_token = evs.get('nextPageToken')
        events.extend(evs["items"])
        if not page_token:
            break
    return events

main()
