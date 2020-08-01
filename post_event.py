from __future__ import print_function
import xml.etree.ElementTree as ET
import pickle
import os.path
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from ics import Calendar
import requests
from googleapiclient.errors import HttpError
from urllib3.exceptions import NewConnectionError
from my_logger import MyLogger
import arrow
import atexit

MONTHS_FWD = 12
MONTHS_BACK = 2
TODAY = arrow.now()
START_DATE = TODAY.shift(months=+MONTHS_BACK)
END_DATE = TODAY.shift(months=+MONTHS_FWD)

NM_SPS = {"ss": "urn:schemas-microsoft-com:office:spreadsheet"}

TIMEZONE = 'Europe/Oslo'
T_FORMAT = "YYYY-MM-DDTHH:mm:ssZZ"
D_FORMAT = "YYYY-MM-DD"

START_IN = 0
END_IN = 1
NAME_IN = 2
CLUB_IN = 3
DISTRICT_IN = 4
DISTANCE_IN = 7
INFO_IN = 11

log_obj = MyLogger("mlog", cre_f_ha=False, cre_sys_h=True, root="logs/", sys_ha="INFO", f_ha="DEBUG", 
	logger_level="DEBUG", o_write_all=False)
log_obj.add_handler(level="WARNING", filename="err.log")
log_obj.add_handler(level="INFO", filename="info.log")
log_obj.add_handler(level="DEBUG", filename="all.log")
mlog = log_obj.retrieve_logger()

def main():
	mlog.info("LOG START")
	atexit.register(log_end)

	try:
		service = setup()
	except Exception as e:
		mlog.critical("Could not initialize connection. Aborting:\n{}".format(e))
		exit(3)
	new_events = get_events()
	uploaded_events = get_uploaded_events(service)
	parse_events(service, new_events, uploaded_events)

def log_end():
	mlog.info("LOG END\n\n")

def post_event(service, event, action="upload"):
	mlog.info("Posting event \"{}\" ({}) with action: {}".format(event["summary"], event["start"], action))

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
	except NewConnectionError as err:
		mlog.error(err)
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
							mlog.debug("Event \"{}\" {} has changed!".format(new_event["summary"],
								new_event["start"]))
							mlog.debug("New: \"{}\"".format(new_event[e]))
							mlog.debug("Prev. uploaded: \"{}\"".format(uploaded_event[e]))
							post_event(service, new_event, "update") 
							break
					except KeyError as e:
						mlog.warning("Tag does not exist: %s" % e)

				ignore_events.append(uploaded_event)
				ignore_events.append(new_event)
				break

	mlog.debug("Ignoring following events: {}".format(ignore_events))
	mlog.info("Deleting remaining previously uploaded events")
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
	mlog.info("Setting up connection")
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



# Gets ics- and xml-information for chosen dates, extracts relevant information, and returns list of pakcets in appropriate format
def get_events():
 
	ics_evs = get_events_ics()
	xml_evs = get_events_xml()

	if (len(xml_evs) != len(ics_evs)):
		mlog.critical("XML and ICS do not coincide. Aborting.")
		exit()

	mlog.info("Making event structs")
	events = []

	for i in range(len(xml_evs)):
		ics_ev = ics_evs[i]
		xml_ev = xml_evs[i]
		xml_info = xml_ev_info(xml_ev)

		if skip_event(xml_info, ics_ev):
			mlog.debug("Skipping event: \"{}\"".format(xml_info[NAME_IN]))
			continue

		name_list = ics_ev.name.split(", ")
		summary = '{} ({})'.format("".join(name_list[:-1]), name_list[-1])
		e_id = ics_ev.uid.split("@")[0].lower().replace('_', '')
		time = get_time_format(xml_info[START_IN], xml_info[END_IN])

		e_pkt = make_packet(summary, ics_ev.url, e_id, time, ics_ev.geo, xml_info[INFO_IN])
		events.append(e_pkt)

	mlog.debug(events)
	return events

# Get .ics file from site (with events within specified dates), and make dictionary with
# formatting matched to that of google events with relevant info for each event, and return 
# list. ID is changed to fit limitations in google calendar id pattern.
def get_events_ics():
	mlog.info("Downloading ICS-events")

	url = 'https://eventor.orientering.no/Events/ExportICalendarEvents?startDate={}&endDate={}&organisations=5%2C19&classifications=International%2CChampionship%2CNational%2CRegional%2CLocal'\
		.format(START_DATE.format(D_FORMAT), END_DATE.format(D_FORMAT))
	response = requests.get(url)
	response.encoding = 'utf-8'
	c = Calendar(response.text)
	mlog.debug(response.text)

	ics_evs = list(c.timeline)
	return ics_evs


# Returns ElementTree object of all event-rows in xml document
def get_events_xml():
	mlog.info("Downloading XML-events")

	# nasjonale løp østfold++
	# organisations=4%2C3%2C12%2C20&classifications=International%2CChampionship%2CNational
	url = 'https://eventor.orientering.no/Events/ExportToExcel?startDate={}&endDate={}&organisations=5%2C19&classifications=International%2CChampionship%2CNational%2CRegional%2CLocal'\
		.format(START_DATE.format(D_FORMAT), END_DATE.format(D_FORMAT))
	response = requests.get(url)
	response.encoding = 'utf-8'
	mlog.debug(response.text)

	root = ET.fromstring(response.text)
	# root = tree.getroot()
	table = root.find("./ss:Worksheet[@ss:Name=\"Konkurranser\"]/ss:Table", NM_SPS)
	# First row contains info on structure
	xml_evs = table.findall("ss:Row", NM_SPS)[1:]

	return xml_evs

#Skip events that are cancelled
def skip_event(xml, ics):
	info = xml[INFO_IN]
	start = xml[START_IN]
	maps = ics.geo
	dist_from_now = arrow.now() - xml[START_IN]

	if (info and ("avlys" in info.lower()) or "avlys" in xml[NAME_IN].lower()):
		return True
	if maps == None and dist_from_now.days < 30:
		mlog.debug("Lacking maps and less than 30 days")
		return True
	return False



# Returns upload-ready dictionary with information in appropriate format.
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
		mlog.warning(e)  

	return info

# Parses xml-sub-tree for event and returns contained information in list. Converts time to array-format
def xml_ev_info(xml_ev):
	tree = xml_ev
	info = []

	for node in tree:
		info.append(node.findtext("./ss:Data", namespaces=NM_SPS))

	info[START_IN] = arrow.get(info[START_IN], tzinfo=TIMEZONE)
	if info[END_IN] == None:
		if info[START_IN].timetuple().tm_hour == 0:
                        days_hrs = [1,0]
		else:
                        days_hrs = [0,4]
		info[END_IN] = info[START_IN].shift(days=days_hrs[0], hours=days_hrs[1])
	else:
		info[END_IN] = arrow.get(info[END_IN], tzinfo=TIMEZONE)
	return info

# Change time format to fit google event specifications. Change to date-format (as opposed
# to datetime), if events start and end at midnight (00/24)
def get_time_format(start, end):
	s_date = start
	e_date = end

	if (s_date.timetuple().tm_hour == e_date.timetuple().tm_hour == 0):
		start = {'date': s_date.format(D_FORMAT)}
		end = {'date': e_date.format(D_FORMAT)}
	else:
		start = {
			'dateTime': s_date.format(T_FORMAT), 
			'timeZone': TIMEZONE
			}
		end = {
			'dateTime': e_date.format(T_FORMAT), 
			'timeZone': TIMEZONE
			}
	return [start, end]

# Fetch list of all events from chosen Google calendar in specified time frame, and return list
def get_uploaded_events(service):
	tmax = END_DATE.format(T_FORMAT)
	tmin = START_DATE.format(T_FORMAT)

	events = []
	page_token = None
	while True:
		try:
			evs = service.events().list(calendarId='primary', pageToken=page_token, timeMin=tmin,
					timeMax=tmax, showDeleted=True).execute()
		except Exception as e:
			mlog.error(e)
		page_token = evs.get('nextPageToken')
		events.extend(evs["items"])
		if not page_token:
			break

	mlog.debug(events)
	return events

main()
