#! /bin/bash

# Run script.
python3 post_event.py
ret_val=$?

#Only run check if internet (script sends email)
wget -q --spider http://google.com
if [[ $? -eq 0 ]]
then
    python3 check_last_run.py
    check_val=$?
fi

#Script deactivated because limit already set in script by timedrotatinghandler
# Move all old logs into archive folder, send fail messages down the rabbit hole
#mv ./logs/*.log.* ./logs/archive/ 2>/dev/null

#Exit with 'worst' exit code
exit_val=$ret_val
if [[ $check_val -ne 0 ]]
then
    exit_val=$check_val
fi

exit $exit_val
