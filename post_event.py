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
from my_logger import MyLogger

MONTHS_FWD = 12
MONTHS_BACK = 2

log_obj = MyLogger("mlog", True, full_log_level="INFO", full_file="./logs/full.log", 
    err_file="./logs/err.log")
mlog = log_obj.retrieve_logger()

def main():
    mlog.info("LOG START")

    service = setup()

    today = datetime.today()
    start = today - relativedelta(months=MONTHS_BACK)
    end = today + relativedelta(months=MONTHS_FWD)

    new_events = get_events(today, start, end)
    uploaded_events = get_uploaded_events(service, today, start, end)

    # for ev in uploaded_events:
    #     post_event(service, ev, "delete")
    # exit()

    mlog.debug(uploaded_events)
    mlog.debug(new_events)
    parse_events(service, new_events, uploaded_events)

    # for event in new_events:
    #     exists = check_existence(service, event, uploaded_events)
    #     mlog.debug(uploaded_events[0])
    #     exit()
    #     if exists != None:
    #         post_event(service, event, exists)

    # for event in uploaded_events:
    #     try:
    #         if "still_exists" not in event.keys() and event["source"]["title"] == "Eventor-arrangement":
    #             mlog.info("deleting event:")
    #             mlog.info(event)
    #             service.events().delete(calendarId='primary', eventId=event["id"]).execute()
    #     except Exception as e:
    #         mlog.error("%s" % e)

    mlog.info("LOG END\n\n")

def post_event(service, event, action="upload"):
    mlog.info("Posting event {} ({}) with action: {}".format(event["summary"], event["start"], action))
    try:
        if action == "upload":
            event = service.events().insert(calendarId='primary', body=event).execute()
        elif action == "update":
            event = service.events().update(calendarId='primary', eventId=event["id"], 
                body=event).execute()
        elif action == "delete":
            service.events().delete(calendarId='primary', eventId=event["id"]).execute()
        else:
            mlog.error("Wrong parameter value [upload|update|delete]: %s" % action)
    except HttpError as err:
        mlog.error("%s" % err)

def parse_events(service, new_events, uploaded_events):
    mlog.info("Parsing events")

    ignore_events = []
    for new_event in new_events:
        for uploaded_event in uploaded_events:
            if new_event["id"] == uploaded_event["id"]:
                for e in new_event:
                    mlog.debug(new_event[e])
                    mlog.debug(uploaded_event[e])
                    try:
                        if new_event[e] != uploaded_event[e]:
                            mlog.info("Event {} {} has changed!".format(new_event["summary"],
                                new_event["start"]))
                            post_event(service, new_event, "update") 
                            break
                    except KeyError as e:
                        mlog.warning("Tag does not exist: %s" % e)

                ignore_events.append(uploaded_event)
                ignore_events.append(new_event)
                break

    mlog.info("Deleting remaining previously uploaded events")
    for rem_ev in uploaded_events:
        if rem_ev not in ignore_events and rem_ev["status"] != "cancelled":
            post_event(service, rem_ev, "delete")
    mlog.info("Uploading remaining new events")
    for rem_ev in new_events:
        if rem_ev not in ignore_events:
            post_event(service, rem_ev, "upload")
    return

# Check if event from downloaded ics-file already exists online.
def check_existence(service, new_event, uploaded_events):
    service = service
    new_event = new_event

    for uploaded_event in uploaded_events:
        if new_event["id"] == uploaded_event["id"]:
            uploaded_event["still_exists"] = True
            mlog.debug(uploaded_event)

            for e in new_event:
                try:
                    if new_event[e] != uploaded_event[e]:
                        mlog.debug("Event has changed!")
                        return True
                except KeyError as e:
                    mlog.warning("Tag does not exist: %s" % e)
                    mlog.debug("New event: %s" % new_event)

            return None

    mlog.info("New event")
    mlog.debug(new_event)
    return False

# Post event either by updating existing, or creating new event
def post_event_old(service, event, exists):
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
        mlog.error("%s" % err)

    #TODO: in except: remove from trash
    mlog.debug('Event created: %s' % (event.get('htmlLink')))
    mlog.debug(event.get('id'))


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

    return build('calendar', 'v3', credentials=creds, cache_discovery=False)


# Get .ics file from site (with events from now and three months forward), and make dictionary with relevant info for each event, and return list
# Id is changed to fit limitations in google calendar id pattern.
def get_events(today, start, end):

    today = today
    start_date = start
    end_date = end

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

        try:
            info = {
                'summary': '{} ({})'.format("".join(summary[:-1]), summary[-1]),
                "source": {
                    'title': 'Eventor-arrangement',
                    'url': event.url
                    },
                'id': event.uid.split("@")[0].lower().replace('_', ''),
                'description': 'Se {} for mer informasjon'.format(event.url),
                "start": time[0],
                "end": time[1]
                }
            if event.geo:
                info.update({"location": "{}, {}".format(event.geo[0], event.geo[1])})
        except TypeError as e:
            mlog.warning("%s" % e)

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
def get_uploaded_events(service, today, start, end):
    tmax = end.isoformat('T') + "Z"
    tmin = start.isoformat('T') + "Z"

    events = []
    page_token = None
    while True:
        evs = service.events().list(calendarId='primary', pageToken=page_token, timeMin=tmin,
                timeMax=tmax, showDeleted=True).execute()
        page_token = evs.get('nextPageToken')
        events.extend(evs["items"])
        if not page_token:
            break
    return events

main()
