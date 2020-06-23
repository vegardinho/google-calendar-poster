from __future__ import print_function
import xml.etree.ElementTree as ET
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
import arrow

MONTHS_FWD = 12
MONTHS_BACK = 2
TODAY = datetime.today()
START_DATE = TODAY - relativedelta(months=MONTHS_BACK)
END_DATE = TODAY + relativedelta(months=MONTHS_FWD)
NM_SPS = {"ss": "urn:schemas-microsoft-com:office:spreadsheet"}

log_obj = MyLogger("mlog", cre_f_ha=True, cre_sys_h=True, root="logs/", sys_ha="INFO", f_ha="DEBUG", 
    logger_level="DEBUG", o_write_all=True)
log_obj.add_handler(level="INFO", filename="info.log")
log_obj.add_handler(level="WARNING", filename="err.log")
mlog = log_obj.retrieve_logger()

def main():
    mlog.info("LOG START")

    service = setup()
    new_events = get_events()
    uploaded_events = get_uploaded_events(service)
    parse_events(service, new_events, uploaded_events)

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
        # Error code 409 implies existing event online
        if err.resp.status == 409:
            mlog.info("Attempting to repost by update")
            post_event(service, event, "update")


# Loop through all previously uploaded events for every new event, to see if it already exists; 
# if so, update if changed. Delete all remaining events previously uploaded and not matched; 
# upload all remaining new events not matched
def parse_events(service, new_events, uploaded_events):
    mlog.info("Parsing events")
    ignore_events = []
    for new_event in new_events:
        for uploaded_event in uploaded_events:
            if new_event["id"] == uploaded_event["id"]:
                mlog.debug("Event \"{}\" ({}) found in previously uploaded events".format(new_event["summary"],
                    new_event["start"]))
                for e in new_event:
                    try:
                        if new_event[e] != uploaded_event[e] or uploaded_event["status"] == "cancelled":
                            mlog.info("Event {} {} has changed!".format(new_event["summary"],
                                new_event["start"]))
                            mlog.debug("New: {}".format(new_event[e]))
                            mlog.debug("Prev. uploaded: {}".format(uploaded_event[e]))
                            post_event(service, new_event, "update") 
                            break
                    except KeyError as e:
                        mlog.warning("Tag does not exist: %s" % e)

                ignore_events.append(uploaded_event)
                ignore_events.append(new_event)
                break

    mlog.info("Deleting remaining previously uploaded events")
    mlog.debug("Ignored events:")
    mlog.debug(ignore_events)
    for rem_ev in uploaded_events:
        if rem_ev not in ignore_events and rem_ev["status"] != "cancelled":
            post_event(service, rem_ev, "delete")
    mlog.info("Uploading remaining new events")
    for rem_ev in new_events:
        if rem_ev not in ignore_events:
            post_event(service, rem_ev, "upload")
    return


# Setup communication channel with google calendar
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

# Get .ics file from site (with events within specified dates), and make dictionary with
# formatting matched to that of google events with relevant info for each event, and return 
# list. ID is changed to fit limitations in google calendar id pattern.
def get_events_ics():
    mlog.info("Downloading ICS-events")

    url = 'https://eventor.orientering.no/Events/ExportICalendarEvents?startDate={}&endDate={}&organisations=5%2C19&classifications=International%2CChampionship%2CNational%2CRegional%2CLocal'\
        .format(START_DATE, END_DATE)
    response = requests.get(url)
    response.encoding = 'utf-8'
    c = Calendar(response.text)

    ics_evs = list(c.timeline)
    return ics_evs


def get_events_xml():
    mlog.info("Downloading XML-events")

    url = 'https://eventor.orientering.no/Events/ExportToExcel?startDate={}&endDate={}&organisations=5%2C19&classifications=International%2CChampionship%2CNational%2CRegional%2CLocal'\
        .format(START_DATE, END_DATE)
    response = requests.get(url)
    response.encoding = 'utf-8'
    mlog.debug(response.text)


    root = ET.fromstring(response.text)
    # root = tree.getroot()
    table = root.find("./ss:Worksheet[@ss:Name=\"Konkurranser\"]/ss:Table", NM_SPS)
    # First row contains info on structure
    xml_evs = table.findall("ss:Row", NM_SPS)[1:]

    return xml_evs

def get_events():
    START_IND = 0
    END_IND = 1
    NAME_IN = 2
    CLUB_IN = 3
    DISTRICT_IN = 4
    DISTANCE_IN = 7
    INFO_IN = 11

    xml_evs = get_events_xml()
    ics_evs = get_events_ics()

    if (len(xml_evs) != len(ics_evs)):
        mlog.critical("XML and ICS do not coincide. Aborting.")
        exit()

    mlog.info("Making event structs")
    events = []

    for i in range(len(xml_evs)):
        ics_ev = ics_evs[i]
        xml_ev = xml_evs[i]

        #Skip events that are cancelled
        xml_info = xml_ev_info(xml_ev, START_IND, END_IND)
        info = xml_info[INFO_IN]
        if (info and ("avlys" in info.lower()) or "avlys" in xml_info[NAME_IN].lower()):
            continue

        name_list = ics_ev.name.split(", ")
        summary = '{} ({})'.format("".join(name_list[:-1]), name_list[-1])
        e_id = ics_ev.uid.split("@")[0].lower().replace('_', '')
        time = get_time_format(xml_info[START_IND], xml_info[END_IND])

        e_pkt = make_packet(summary, ics_ev.url, e_id, time, ics_ev.geo, xml_info[INFO_IN])
        events.append(e_pkt)

    mlog.debug(events)
    return events

def make_packet(summary, e_url, e_id, time, e_geo, e_info):
    try:
        info = {
            'summary': summary,
            "source": {
                'title': 'Eventor-arrangement',
                'url': e_url
                },
            'id': e_id,
            'description': 'Se <a href="{0}" target="_blank">{0}</a> for mer informasjon'.format(e_url),
            "start": time[0],
            "end": time[1]
            }
        if e_geo:
            info.update({"location": "{}, {}".format(e_geo[0], e_geo[1])})
        if e_info:
            info['description'] = "{}\n\n{}".format(e_info, info['description'])
    except TypeError as e:
        mlog.warning("%s" % e)  

    return info

def xml_ev_info(xml_ev, START_IND, END_IND):
    tree = xml_ev
    info = []

    for node in tree:
        info.append(node.findtext("./ss:Data", namespaces=NM_SPS))

    info[START_IND] = arrow.get(info[START_IND])
    if info[END_IND] == None:
        if info[START_IND].timetuple().tm_hour == 0:
            add_delta = relativedelta(days=1)
        else:
            add_delta = relativedelta(hours=4)
        info[END_IND] = info[START_IND] + add_delta
    else:
        info[END_IND] = arrow.get(info[END_IND])
    info[END_IND] = info[END_IND].replace(tzinfo='Europe/Oslo')
    info[START_IND] = info[START_IND].replace(tzinfo='Europe/Oslo')
    return info

# Change time format to fit google event specifications. Change to date-format (as opposed
# to datetime), if events start and end at midnight (00/24)
def get_time_format(start, end):
    s_date = start
    e_date = end

    if (s_date.timetuple().tm_hour == e_date.timetuple().tm_hour == 0):
        start = {'date': s_date.format("YYYY-MM-DD")}
        end = {'date': e_date.format("YYYY-MM-DD")}
    else:
        start = {
            'dateTime': s_date.format("YYYY-MM-DDTHH:mm:ssZZ"), 
            'timeZone': 'Europe/Oslo'
            }
        end = {
            'dateTime': e_date.format("YYYY-MM-DDTHH:mm:ssZZ"), 
            'timeZone': 'Europe/Oslo'
            }
    return [start, end]

# Fetch list of all events from chosen Google calendar in specified time frame, and return list
def get_uploaded_events(service):
    tmax = END_DATE.isoformat('T') + "Z"
    tmin = START_DATE.isoformat('T') + "Z"

    events = []
    page_token = None
    while True:
        evs = service.events().list(calendarId='primary', pageToken=page_token, timeMin=tmin,
                timeMax=tmax, showDeleted=True).execute()
        page_token = evs.get('nextPageToken')
        events.extend(evs["items"])
        if not page_token:
            break

    mlog.debug(events)
    return events

main()
