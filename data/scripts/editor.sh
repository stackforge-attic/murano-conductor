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
#    System EDITOR variable replacement for virsh usage
#
INPUT_DATA=$1
if [ -n "$EDITMODE" ]; then
	case $EDITMODE in
		add )
			echo "Add requested"
				sed -e '/IP/a\    <parameter name="IP" value="'$(echo $ADDR)'"/>' -i $INPUT_DATA	
		;;

		remove ) 
			echo "Remove requested"
                                sed -e '/'$(echo $ADDR)'/d' -i $INPUT_DATA
		;;
	esac
else
	echo -e "env VAR EDITMODE unset, exiting!"
	exit 1	
fi
