#!/bin/bash
#    Copyright (c) 2013 Mirantis, Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
#    Author: Igor Yozhikov <iyozhikov@mirantis.com>  
#
#    Before using TO-DO:
#    1. Add on all "Compute" nodes some user and assign it to libvirtd gorup 
#    via command like this: "usermod -G libvirtd -a username"
#    2. Generate SSH key-pairs on "Controller" node, operate from "Controller" node is more prefered
#    "ssh-keygen -f id_rsa -C 'Some comment' -N '' -t rsa -q"
#    3. Add id_rsa.pub key into ~user/.ssh/authorized_keys on each "Compute" node and chmod it to 600
#    4. Check ssh connection works with keys, generated previously.
#    5. Make/Set proper Openstack credentials file and change OS_CREDS_FILE variable.
#    6. Pray :)
#
#	
# Configuration
RUNNING_DIR=$(cd $(dirname "$0") && pwd)
RESERVATIONS_FILE=$RUNNING_DIR/reserved_addr

# source openstack credentials file
OS_CREDS_FILE="/home/stack/devstack/openrc"
if [ ! -f "$OS_CREDS_FILE" ];then
 	echo -e "Set proper openstack credentials file path, file \"$OS_CREDS_FILE\" - not found, exiting!"
	exit 1
fi
source $OS_CREDS_FILE admin admin



# search in openstack cli utils output
function get_field_by_num()
{
	# Params are: 1 - field to output, 2 - field to search, everything else - command to execute
	FN=$1
	SRCH_STR=$2
	shift 2
	PARAMS=$@
	_result=$($PARAMS | sed -e'/^+/,/+$/d'| grep $SRCH_STR  | awk '{print $'$(echo $FN*2 | bc)'}')
	if [ -n "$_result" ]; then
		echo $_result
	fi
}
# output vm-uuid vm-instance-name vm-hypervisor-host-name
function get_vm_info()
{
	vm_uuid=$1
	_vm_host=""
	_vm_instance_name=""
	nova show $vm_uuid | \
	{
	while read line
	do
		_tmp=$(get_field_by_num 2 ':host' "echo \"$line\"")
		if [ -n "$_tmp" ]; then
			_vm_host=$_tmp
			unset _tmp
		fi
		_tmp=$(get_field_by_num 2 ':instance_name' "echo \"$line\"")
		if [ -n "$_tmp" ]; then
                	_vm_instance_name=$_tmp
	                unset _tmp
	        fi
	done	
	echo "$vm_uuid $_vm_instance_name $_vm_host"
	}
}

# get not used IP from fixed range and save in nova & local file
function get_free_fixed_addr()
{
	_reservation_file="$RESERVATIONS_FILE"
	_instances=$@
	if [ -f "$_reservation_file" ]; then
		_reserved_ips=$(echo $(cat $_reservation_file | awk '{print $1}') | tr " " "|")
		if [ -n "$_reserved_ips" ];then
			_addr=$(nova-manage fixed list 2>/dev/null | grep -E '[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[2-9]{1,3}' | grep -v -E "$_reserved_ips" | grep -m 1 None | awk '{print $2}')
		else
			_addr=$(nova-manage fixed list 2>/dev/null | grep -E '[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[2-9]{1,3}' | grep -m 1 None | awk '{print $2}')
		fi
	else
		_addr=$(nova-manage fixed list 2>/dev/null | grep -E '[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[2-9]{1,3}' | grep -m 1 None | awk '{print $2}')
		touch $_reservation_file
	fi
	if [ -n "$_addr" ]; then
		echo $_addr
	else
		echo -e "Error, while getting free ip from fixed range, exiting!"
		exit 1
	fi
}

# reserve ip
function save_reserved_ip()
{
	_IPADDR=$1
	shift
	_instances=$@
	_reservation_file="$RESERVATIONS_FILE"
        nova fixed-ip-reserve $_IPADDR
        if [ $? -ne 0 ]; then
        	echo -e "Reservation for ip address \"$_IPADDR\" in NOVA fails, exiting!"
                exit 1
	else
		echo -e "$_IPADDR\t$_instances" >> $_reservation_file
        fi
}

# get libvirt nwfilter uuid
function get_nwfilter_uuid()
{
	_instance_name=$2
	_libvirt_host=$3
	if [ -z $_libvirt_host ]; then
		_result=$(virsh nwfilter-list | grep $_instance_name | awk '{print $1}')
	else
		_result=$(virsh --connect=qemu+ssh://$_libvirt_host/system nwfilter-list | grep $_instance_name | awk '{print $1}')
	fi
	if [ $? -eq 0 ]; then
		echo $_result
	else
		echo "Error during requesting libvirt network filer list, exiting!"
		exit 1
	fi
}

# validate ip
function valid_ip()
{
    local  ip=$1
    local  stat=1

    if [[ $ip =~ ^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$ ]]; then
        OIFS=$IFS
        IFS='.'
        ip=($ip)
        IFS=$OIFS
        [[ ${ip[0]} -le 255 && ${ip[1]} -le 255 \
            && ${ip[2]} -le 255 && ${ip[3]} -le 255 ]]
        stat=$?
    fi
    return $stat
}

# get instance names with given ip
function get_instances_with_reserved_ip()
{
	_IPADDR=$1
	_reservation_file="$RESERVATIONS_FILE"
	if [ "$(cat $_reservation_file | wc -l)" -eq 0 ];then
		exit 1
        else
		lines=$(sed -ne '/'$_IPADDR'/ =' $_reservation_file)
		if [ -n $lines ]; then
			_data=$(sed -ne "$lines"p $_reservation_file)
			_instances=$(echo $_data | awk '{if ((NF - 1) == 1){print $NF;} else {print $(NF-1),$NF;}}')
			echo $_instances
		else
			echo "Nothing found for given ip \"$_IPADDR\", exiting!"
			exit 1
		fi
	fi 
}

# delete reservation
function delete_reservation()
{
	_IPADDR=$1
	_reservation_file="$RESERVATIONS_FILE"
	if [ "$(cat $_reservation_file | wc -l)" -eq 0 ];then
		 echo "No any records in \"$_reservation_file\"."
	else
	        lines=$(sed -ne '/'$_IPADDR'/ =' $_reservation_file)
	        if [ -n $lines ]; then
        	        sed -ne "$lines"d -i $_reservation_file
			if [ $? -ne 0 ]; then
				echo "Deleting informations about \"$_IPADDR\" from \"$_reservation_file\" fails, exiting!"
				exit 1
			fi
        	else
                	echo "Nothing found for given ip \"$_IPADDR\", exiting!"
	                exit 1
        	fi
	fi
	nova fixed-ip-unreserve $_IPADDR
	if [ $? -ne 0 ]; then
        	echo "Deleting informations about \"$_IPADDR\" from NOVA fails, exiting!"
                exit 1
        fi
}

# show reservations from file
function show_reserved()
{
	_reservation_file="$RESERVATIONS_FILE"
	if [ "$(cat $_reservation_file | wc -l)" -eq 0 ];then
		echo "No any records in \"$_reservation_file\"."
	else
		_ln=1
		cat $_reservation_file |\
		{
			while read line
			do	
				_ip_addr=$(echo $line | awk '{print $1}')
				_instances=$(echo $line | awk '{if ((NF - 1) == 1){print $NF;} else {print $(NF-1),$NF;}}' | tr " " ",")	
				echo -e "record=\"$_ln\"; ip=\"$_ip_addr\"; instances=\"$_instances\""
				_ln=$(echo $_ln+1 | bc)	
			done
		}
	fi
}


# edit libvirt nwfilter
function edit_nwfilter()
{
	export EDITOR=$RUNNING_DIR/editor.sh
	export EDITMODE=$3
	export ADDR=$2
	_filter_uuid=$1
	virsh nwfilter-edit $_filter_uuid
}

# Start main logic
# get action addip or removeip
ACTION=$1
shift
case $ACTION in 
	addip)
		_INSTANCES=$@
		_IP_ADDR=$(get_free_fixed_addr $_INSTANCES)
		for _instance in $_INSTANCES
		do
			echo -e "Add address \"$_IP_ADDR\" filter entry for \"$_instance\"..."
                        _vm_uuid=$(get_field_by_num 1 $_instance "nova list")
                        _vm_params=$(get_vm_info $_vm_uuid)
                        _nwfilter=$(get_nwfilter_uuid $_vm_params)
                        edit_nwfilter $_nwfilter $_IP_ADDR "add"
		done
		save_reserved_ip $_IP_ADDR $_INSTANCES
	;;

	removeip)
		_IPADDR=$1
		if valid_ip $_IPADDR; then
			_INSTANCES=$(get_instances_with_reserved_ip $_IPADDR)
			if [ -n "$_INSTANCES" ]; then
				for _instance in $_INSTANCES
		                do
        		                echo -e "Removing address \"$_IPADDR\" filter entry for \"$_instance\"..."
					_vm_uuid=$(get_field_by_num 1 $_instance "nova list")
					_vm_params=$(get_vm_info $_vm_uuid)
					_nwfilter=$(get_nwfilter_uuid $_vm_params)
					edit_nwfilter $_nwfilter $_IPADDR "remove"
        	        	done
				delete_reservation $_IPADDR
			else
				echo -e "Nothing found for address \"$_IPADDR\"."
			fi
		else
			echo -e "Ip address entered is not in valid format, exiting!"
			exit 1
		fi
	;;
	
	showreserved)
		echo -e "Addresses in reservations..."
		show_reserved
	;;
	
	*)
		echo -e "Usage $(basename "$0") command \nCommands:\n\taddip instance_name1 [instance_nameN]\n\tremoveip ip_address\n\tshowreserved - show records about reserved addresses"
		exit 1
	;;
esac
