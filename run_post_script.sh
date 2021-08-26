#! /bin/bash

# Run script 
cd /home/pi/Documents/google-calendar-poster/
python3 post_event.py
ret_val=$?


# Run check of last successfull run if failed run and internet connection
if [ $ret_val -eq 0 ]
then
	exit_val=0
else
	wget -q --spider http://google.com
	if [[ $? -eq 0 ]]
	then
		python3 check_last_run.py
	fi
	exit_val=-1
fi

# Move all old logs into archive folder
mv ./logs/*.log.* ./logs/archive/

deactivate
exit $exit_val
