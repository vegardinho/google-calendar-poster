from __future__ import print_function
from datetime import date,timedelta
import pickle
import os.path
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from ics import Calendar
import requests
import googleapiclient.errors

def main():
    service = setup()
    new_events = get_events()
    old_events = get_old_events(service)

    manage_events(service, new_events, old_events)

def manage_events(service, new_events, old_events):
    service = service
    new_events = new_events
    old_events = old_events

    for event in new_events:
        exists = check_existance(service, event, old_events)
        post_event(service, event, exists)

def check_existance(service, new_event, old_events):
    service = service
    new_event = new_event
    old_events = old_events

    for event in old_events:
        if event["id"] == new_event["id"]:
            print("Event exists")
            return True
        # import pprint
            # pp = pprint.PrettyPrinter(indent=3)
            # pp.pprint(new_event)
            # print()
            # pp.pprint(event)
            # print("\n\n")
            #
            # for id,val in enumerate(new_event): 
            #     if val not in enumerate(event):
            #         print("Event {} has changed".format(event["id"]))
            #         return True
            # print("Event {} has not changed".format(event["id"]))
            # return None

    print("New event")
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


def post_event(service, event, exists):
    exists = exists
    e = event
    service = service
    # print(e["name"])
    # print(e["start"])
    # print(e["end"])
    # return

    event_body = {
            'summary': '{} ({})'.format(e["name"], e["club"]),
            'location': e["geo"],
            'id': e["id"],
            'source': {
                'title': 'Eventor',
                'url': e["url"]
                },
            'description': 'Se Eventor for mer informasjon',
            'start': e["start"],
            'end': e["end"]
            }

    if exists == True:
        event = service.events().update(calendarId='primary', eventId=event_body["id"], body=event_body).execute()
    elif exists == False:
        event = service.events().insert(calendarId='primary', body=event_body).execute()

    print('Event created: %s' % (event.get('htmlLink')))
    print(event.get('id'))


def get_events():
    #Use https://icspy.readthedocs.io/en/stable/

    start_date = date.today()
    end_date = date.today().replace(month=(start_date.month + 4))
    url = 'https://eventor.orientering.no/Events/ExportICalendarEvents?startDate={}&endDate={}&organisations=19&classifications=International%2CChampionship%2CNational%2CRegional%2CLocal'.format(
            start_date, end_date)
    response = requests.get(url)
    response.encoding = 'utf-8'
    c = Calendar(response.text)

    # f = open('~/Downloads/Events.ics', 'r').read()

    eventorEv = list(c.timeline)
    events = []

    for event in eventorEv:
        summary = event.name.split(", ")
        # 2020-04-27 22:00:00+00:00
        # 1996-12-19T16:39:57
        events.append({
            "name": ", ".join(summary[:-1]), 
            "club": summary[-1], 
            "geo": event.location,
            "url": event.url,
            'id': event.uid.split("@")[0].lower().replace('_', ''),
            "start": {
                'dateTime': event.begin.format("YYYY-MM-DDTHH:mm:ss"), 
                'timeZone': 'Europe/Oslo'
                },
            "end": {
                'dateTime': event.end.format("YYYY-MM-DDTHH:mm:ss"), 
                'timeZone': 'Europe/Oslo'
                }
            })

    # print(events)
    return events

def get_old_events(service):
    service = service

    events = []
    page_token = None
    while True:
        evs = (service.events().list(calendarId='primary', pageToken=page_token).execute())
        page_token = evs.get('nextPageToken')
        events.extend(evs["items"])
        if not page_token:
            break
    return events

main()
