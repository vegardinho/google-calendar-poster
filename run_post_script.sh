#! /bin/bash

cd /Users/vegardlandsverk/Documents/Progging/google_calendar
source bin/activate
python3 post_event.py
ret_val=$?
deactivate

exit $ret_val
