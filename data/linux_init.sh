#!/bin/sh

AgentConfigBase64='%AGENT_CONFIG_BASE64%'
service murano-agent stop
echo $AgentConfigBase64 | base64 -d > /etc/murano-agent.conf
service murano-agent start
