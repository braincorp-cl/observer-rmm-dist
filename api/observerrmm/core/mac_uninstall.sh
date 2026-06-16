#!/bin/bash

if [ -f /usr/local/mesh_services/meshagent/meshagent ]; then
  /usr/local/mesh_services/meshagent/meshagent -fulluninstall
fi

if [ -f /opt/observermesh/meshagent ]; then
  /opt/observermesh/meshagent -fulluninstall
fi

launchctl bootout system /Library/LaunchDaemons/observeragent.plist
rm -rf /usr/local/mesh_services
rm -rf /opt/observermesh
rm -f /etc/observeragent
rm -rf /opt/observeragent
rm -f /Library/LaunchDaemons/observeragent.plist