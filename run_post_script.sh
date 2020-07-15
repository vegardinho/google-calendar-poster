#! /bin/bash

cd /Users/vegardlandsverk/Documents/Progging/google_calendar
source bin/activate
python3 post_event.py
ret_val=$?
deactivate

exit $ret_val







# test `find "/Users/vegardlandsverk/Documents/Progging/google_calendar/post_event.py" -amin +1440`
# ran_last_24hrs=$?

#If python script failed because of internet connection, and 
# either argument provided or more than 24hrs since last access, then postpone run
# if [ $ret_val -eq 3 ]
# then
# 	if ! [ -z $1 ] || [ $ran_last_24hrs -eq 0 ]
# 	then
# 		echo eksisterer
# 		#utsett kjøring
# 	fi
# fi
