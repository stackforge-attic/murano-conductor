#!/bin/sh

AgentConfigBase64='%AGENT_CONFIG_BASE64%'

mkdir /etc/murano

echo AgentConfigBase64 | base64 -d > /etc/murano/agent.config