#!/usr/bin/env python3

import xml.etree.ElementTree as ET
import pickle
import traceback
import os.path
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from ics import Calendar
import requests
from googleapiclient.errors import HttpError
from my_logger import MyLogger # type: ignore
from email_errors import email_errors # type: ignore
import arrow
import atexit
import re

EMAIL_ERR_FILE = "./email_err.out"

MONTHS_FWD = 12
MONTHS_BACK = 2
TODAY = arrow.now()
START_DATE = TODAY.shift(months=-MONTHS_BACK)
END_DATE = TODAY.shift(months=+MONTHS_FWD)

NM_SPS = {"ss": "urn:schemas-microsoft-com:office:spreadsheet"}

TIMEZONE = "Europe/Oslo"
T_FORMAT = "YYYY-MM-DDTHH:mm:ssZZ"
D_FORMAT = "YYYY-MM-DD"

START_IDX = 0
END_IDX = 1
NAME_IDX = 2
CLUB_IDX = 3
DISTRICT_IDX = 4
DISTANCE_IDX = 7
INFO_IDX = 11

EVENTOR_URL = "https://eventor.orientering.no/Events/"
EVENTOR_QUERY = f"startDate={START_DATE.format(D_FORMAT)}&endDate={END_DATE.format(D_FORMAT)}&organisations=5%2C19&classifications=International%2CChampionship%2CNational%2CRegional%2CLocal"

EVENTOR_ICS = EVENTOR_URL + "ExportICalendarEvents"
EVENTOR_XML = EVENTOR_URL + "ExportToExcel"

CALENDAR_ID = "primary"
# CALENDAR_ID = '68ca41b7ea965f90ff1baa2a5999a9d69b279553818c5ba2ef60479b6fe02b11@group.calendar.google.com' # Test cal

CRITICAL_LOG_FILE = "logs/critical.log"
ERR_LOG_FILE = "logs/err.log"
INFO_LOG_FILE = "logs/info.log"
DEBUG_LOG_FILE = "logs/all.log"

ERR_EMAIL = "landsverk.vegard@gmail.com"


def retrieve_logger():
    log_obj = MyLogger()
    log_obj.add_handler(level="INFO")
    log_obj.add_handler(level="DEBUG", filename=DEBUG_LOG_FILE)
    log_obj.add_handler(level="INFO", filename=INFO_LOG_FILE)
    log_obj.add_handler(level="ERROR", filename=ERR_LOG_FILE)
    return log_obj.retrieve_logger()


log = retrieve_logger()


def main():
    log.info("LOG START")
    atexit.register(log_end)

    try:
        service = setup()
    except Exception as e:
        log.critical("Could not initialize connection. Aborting:\n{}".format(e))
        email_errors(e, ERR_EMAIL, os.path.abspath(__file__), 
                     EMAIL_ERR_FILE, log, INFO_LOG_FILE)
        exit()
    new_events = get_events()
    uploaded_events = get_uploaded_events(service)
    parse_events(service, new_events, uploaded_events)


def log_end():
    log.info("LOG END\n")


def post_event(service, event, action="upload"):
    start_date = re.search(
        r"\d{4}.\d{2}.\d{2}", str(event["start"])
    ).group()  # Can be either 'date' or 'dateTime'
    log.info(f"{action.capitalize()}: \"{event['summary']}\", {start_date}")

    try:
        if action == "upload":
            event = (
                service.events().insert(calendarId=CALENDAR_ID, body=event).execute()
            )
        elif action == "update":
            event = (
                service.events()
                .update(calendarId=CALENDAR_ID, eventId=event["id"], body=event)
                .execute()
            )
        elif action == "delete":
            service.events().delete(
                calendarId=CALENDAR_ID, eventId=event["id"]
            ).execute()
        else:
            log.error("Wrong parameter value [upload|update|delete]: %s" % action)
            email_errors(e, ERR_EMAIL, os.path.abspath(__file__),
                EMAIL_ERR_FILE, log, INFO_LOG_FILE)
    except Exception as err:
        # Error code 409 implies existing event online
        if type(err) == HttpError and err.resp.status == 409:
            log.warning(err)
            log.info("Attempting to repost by update")
            post_event(service, event, "update")
        else:
            log.error(err)
            email_errors(e, ERR_EMAIL, os.path.abspath(__file__),
                EMAIL_ERR_FILE, log, INFO_LOG_FILE)


# Loop through all previously uploaded events for every new event, to see if it already exists;
# if so, update if changed. Delete all remaining events previously uploaded and not matched;
# upload all remaining new events not matched
def parse_events(service, new_events, uploaded_events):
    log.info("Parsing events")
    ignore_events = []
    for new_event in new_events:
        for uploaded_event in uploaded_events:
            if new_event["id"] == uploaded_event["id"]:
                log.debug(
                    'Event "{}" ({}) found in previously uploaded events'.format(
                        new_event["summary"], new_event["start"]
                    )
                )
                for e in new_event:
                    try:
                        if (
                            new_event[e] != uploaded_event[e]
                            or uploaded_event["status"] == "cancelled"
                        ):
                            log.debug( 'Event "{}" {} has changed!'.format(
                                    new_event["summary"], new_event["start"]
                                )
                            )
                            log.debug('New: "{}"'.format(new_event[e]))
                            log.debug('Prev. uploaded: "{}"'.format(uploaded_event[e]))
                            post_event(service, new_event, "update")
                            break
                    except KeyError as e:
                        log.warning(f"Tag does not exist: {e} ({new_event['summary']}")

                ignore_events.append(uploaded_event)
                ignore_events.append(new_event)
                break

    log.debug("Ignoring following events: {}".format(ignore_events))
    for rem_ev in uploaded_events:
        if rem_ev not in ignore_events and rem_ev["status"] != "cancelled":
            post_event(service, rem_ev, "delete")
    for rem_ev in new_events:
        if rem_ev not in ignore_events:
            post_event(service, rem_ev, "upload")
    return


# Setup communication channel with google calendar
def setup():
    log.info("Setting up connection")
    # If modifying these scopes, delete the file token.pickle.
    SCOPES = ["https://www.googleapis.com/auth/calendar"]

    creds = None
    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.

    if os.path.exists("token.pickle"):
        if os.path.getsize("token.pickle") > 0:
            with open("token.pickle", "rb") as token:
                creds = pickle.load(token)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open("token.pickle", "wb") as token:
            pickle.dump(creds, token)

    return build("calendar", "v3", credentials=creds, cache_discovery=False)


# Gets ics- and xml-information for chosen dates, extracts relevant information, and returns list of pakcets in appropriate format
def get_events():
    ics_evs = get_events_ics()
    xml_evs = get_events_xml()

    if len(xml_evs) != len(ics_evs):
        log.critical("XML and ICS do not coincide. Aborting.")
        email_errors(e, ERR_EMAIL, os.path.abspath(__file__), 
            EMAIL_ERR_FILE, log, INFO_LOG_FILE)
        exit()

    log.info("Making event structs")
    events = []

    for i in range(len(xml_evs)):
        ics_ev = ics_evs[i]
        xml_ev = xml_evs[i]
        xml_info = xml_ev_info(xml_ev)

        if skip_event(xml_info, ics_ev):
            log.debug('Skipping event: "{}"'.format(xml_info[NAME_IDX]))
            continue

        name_list = ics_ev.name.split(", ")
        summary = "{} ({})".format("".join(name_list[:-1]), name_list[-1])
        e_id = ics_ev.uid.split("@")[0].lower().replace("_", "")
        time = get_time_format(xml_info[START_IDX], xml_info[END_IDX])

        e_pkt = make_packet(summary, ics_ev.url, e_id, time, 
                            ics_ev.geo, xml_info[INFO_IDX])
        events.append(e_pkt)

    log.debug(events)
    return events


# Get .ics file from site (with events within specified dates), and make dictionary with
# formatting matched to that of google events with relevant info for each event, and return
# list. ID is changed to fit limitations in google calendar id pattern.
def get_events_ics():
    log.info("Downloading ICS-events")

    response = get_requests_response(EVENTOR_ICS)
    c = Calendar(response.text)
    ics_evs = list(c.timeline)
    return ics_evs


def get_requests_response(URL):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.122 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
    }

    sesh = requests.Session()
    response = sesh.get(
        URL, headers=headers, cookies={"EventsFilterInitState": EVENTOR_QUERY}
    )
    response.encoding = "utf-8"

    log.debug(response.text)
    return response


# Returns ElementTree object of all event-rows in xml document
def get_events_xml():
    log.info("Downloading XML-events")

    response = get_requests_response(EVENTOR_XML)
    root = ET.fromstring(response.text)
    table = root.find('./ss:Worksheet[@ss:Name="Konkurranser"]/ss:Table', NM_SPS)
    # Skip first row, which contains info on structure
    xml_evs = table.findall("ss:Row", NM_SPS)[1:]

    return xml_evs


# Skip events that are cancelled
def skip_event(xml, ics):
    info = xml[INFO_IDX]
    start = xml[START_IDX]
    maps = ics.geo
    dist_from_now = xml[START_IDX] - arrow.now()

    # if (info and ("avlys" in info.lower()) or "avlys" in xml[NAME_IDX].lower()):
    # return True
    if maps == None and 0 < dist_from_now.days < 10 and not info:
        log.warning('Skipping assumed cancelled event: "{}"'.format(xml[NAME_IDX]))
        return True
    return False


# Returns upload-ready dictionary with information in appropriate format.
def make_packet(summary, e_url, e_id, time, e_geo, e_info):
    info = None
    try:
        info = {
            "summary": summary,
            "source": {"title": "Eventor-arrangement", "url": e_url},
            "id": e_id,
            "description": 'Se <a href="{0}" target="_blank">{0}</a> for mer informasjon'.format(
                e_url
            ),
            "start": time[0],
            "end": time[1],
        }
        if e_geo:
            info.update({"location": "{}, {}".format(e_geo[0], e_geo[1])})
        if e_info:
            info["description"] = "{}\n\n{}".format(e_info, info["description"])
    except TypeError as e:
        log.warning(e)

    return info


# Parses xml-sub-tree for event and returns contained information in list. Converts time to array-format
def xml_ev_info(xml_ev):
    tree = xml_ev
    info = []

    for node in tree:
        info.append(node.findtext("./ss:Data", namespaces=NM_SPS))

    info[START_IDX] = arrow.get(info[START_IDX], tzinfo=TIMEZONE)
    if info[END_IDX] == None:
        if info[START_IDX].timetuple().tm_hour == 0:
            days_hrs = [1, 0]
        else:
            days_hrs = [0, 4]
        info[END_IDX] = info[START_IDX].shift(days=days_hrs[0], hours=days_hrs[1])
    else:
        info[END_IDX] = arrow.get(info[END_IDX], tzinfo=TIMEZONE)
    return info


# Change time format to fit google event specifications. Change to date-format (as opposed
# to datetime), if events start and end at midnight (00/24)
def get_time_format(start, end):
    s_date = start
    e_date = end

    if s_date.timetuple().tm_hour == e_date.timetuple().tm_hour == 0:
        start = {"date": s_date.format(D_FORMAT)}
        end = {"date": e_date.format(D_FORMAT)}
    else:
        start = {"dateTime": s_date.format(T_FORMAT), "timeZone": TIMEZONE}
        end = {"dateTime": e_date.format(T_FORMAT), "timeZone": TIMEZONE}
    return [start, end]


# Fetch list of all events from chosen Google calendar in specified time frame, and return list
def get_uploaded_events(service):
    tmax = END_DATE.format(T_FORMAT)
    tmin = START_DATE.format(T_FORMAT)

    evs = None
    events = []
    page_token = None
    while True:
        try:
            evs = (
                service.events()
                .list(
                    calendarId=CALENDAR_ID,
                    pageToken=page_token,
                    timeMin=tmin,
                    timeMax=tmax,
                    showDeleted=True,
                )
                .execute()
            )
        except Exception as e:
            log.error(e)
            email_errors(e, ERR_EMAIL, os.path.abspath(__file__), 
                         EMAIL_ERR_FILE, log, INFO_LOG_FILE)
        page_token = evs.get("nextPageToken")
        events.extend(evs["items"])
        if not page_token:
            break

    log.debug(events)
    return events


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log.error(traceback.format_exc())
        email_errors(e, ERR_EMAIL, os.path.abspath(__file__), 
                     EMAIL_ERR_FILE, log, INFO_LOG_FILE)
