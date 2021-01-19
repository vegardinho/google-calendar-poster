#! /bin/bash

cd /Users/vegardlandsverk/Documents/Progging/google_calendar
source bin/activate
python3 post_event.py
ret_val=$?

if [ $ret_val -eq 0 ]
then
	exit_val=0
else
	/usr/local/bin/wget -q --spider http://google.com
	if [[ $? -eq 0 ]]
	then
		python3 check_last_run.py
	fi
	exit_val=-1
fi

deactivate
exit $exit_val
