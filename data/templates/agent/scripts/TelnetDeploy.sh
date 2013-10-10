#!/bin/sh
#
#
#install app
rpm -aq | grep $1 > /dev/null
if [ $? -ne 0 ];then
    yum install $1 --assumeyes --quiet
    if [ $? -ne 0 ]; then
        echo -e "Can't install $1, exiting..."
        exit 1
    fi
else
    echo "$1 already installed."
fi
#find iptables and add telnet rule
iptcmd=$(which iptables)

if [ -n "$iptcmd" ]; then
    $iptcmd -nvL INPUT | grep "Telnet server access on TCP port 23" > /dev/null
    if [ $? -ne 0 ]; then
        $iptcmd -I INPUT 1 -p tcp -m tcp --dport 23 -j ACCEPT -m comment --comment "Telnet server access on TCP port 23"
        if [ $? -ne 0 ]; then
            echo -e "Can't set $1 access firewall rules, exiting..."
            exit 1
        else
            echo "$iptcmd rule for $1 set."
        fi
    else
        echo "$iptcmd rule for $1 exists."
    fi
else
    echo "There's no iptables found..."
fi

# check telnet start disabled
xinetd_tlnt_cfg=/etc/xinetd.d/telnet
if [ -f "$xinetd_tlnt_cfg" ]; then
    sed -i '/disable.*=/ s/yes/no/' $xinetd_tlnt_cfg
    if [ $? -ne 0 ]; then
        echo "can't modify $xinetd_tlnt_cfg"
        exit 1
    fi
else
    echo "$ serviec startup config not found under $xinetd_tlnt_cfg"
fi
#security tty for telnet
setty=/etc/securetty
lines=$(sed -ne '/^pts\/[0-9]/,/^pts\/[0-9]/ =' $setty)
if [ -z "$lines" ]; then
    cat >> $setty << "EOF"
pts/0
pts/1
pts/2
pts/3
pts/4
pts/5
pts/6
pts/7
pts/8
pts/9
EOF
    if [ $? -ne 0 ]; then
        echo "Error occured during $setty changing..."
    exit 1
fi
else
    echo "$setty has pts/0-9 options..."
fi
#restart xinetd
service xinetd restart
if [ $? -ne 0 ]; then
    echo "Error occured during xinetd restart..."
    exit 1
fi
