#!/bin/bash

#
# Write out to file ${1} and load into slurm account database
#
if [ \! -r app/config.json ]
then
    echo "config file missing or unreadable" >&2
    echo "perhaps you aren't in the correct directory" >&2
    exit 1
fi
echo "generating load file:"
bin/slurm-accounts.py --config=app/config.json all > tmp/accounts.out || \
    ( echo "load file generation failed" >&2 ; exit 1 ;)

echo "loading file into database- ready for password?"
sacctmgr load file=tmp/accounts.out clean Cluster=gizmo

echo "updating local groups file"
bin/account-groups.py > /var/tmp/group.new
if [ \! -s /var/tmp/group.new ]
then
    echo "creating local groups failed" >&2
    exit 1
fi

[ -f /etc/group.5 ] && ( echo rm /etc/group.5; rm /etc/group.5 ;)
for X in {4..2}
do
    if [ -f /etc/group.${X} ]
    then
        echo cp /etc/group.$((${X}-1)) /etc/group.${X}
        cp /etc/group.$((${X}-1)) /etc/group.${X}
    fi
done

echo cp /etc/group /etc/group.1
cp /etc/group /etc/group.1
diff /etc/group /var/tmp/group.new
read
echo cp /var/tmp/group.new /etc/group
cp /var/tmp/group.new /etc/group
echo rm /var/tmp/group.new
rm /var/tmp/group.new
echo "complete"
