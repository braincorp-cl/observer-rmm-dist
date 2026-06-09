package shared

// CheckInNats is sent by the agent on NATS subject "agent-hello".
type CheckInNats struct {
	Agentid string `msgpack:"id"`
	Version string `msgpack:"version"`
}

// PublicIPNats is sent by the agent on NATS subject "agent-publicip".
type PublicIPNats struct {
	Agentid  string `msgpack:"id"`
	PublicIP string `msgpack:"public_ip"`
}

// AgentInfoNats is sent by the agent on NATS subject "agent-agentinfo".
type AgentInfoNats struct {
	Agentid      string  `msgpack:"id"`
	Hostname     string  `msgpack:"hostname"`
	OS           string  `msgpack:"os"`
	Platform     string  `msgpack:"plat"`
	TotalRAM     float64 `msgpack:"total_ram"`
	BootTime     int64   `msgpack:"boot_time"`
	RebootNeeded bool    `msgpack:"needs_reboot"`
	Username     string  `msgpack:"logged_in_username"`
	GoArch       string  `msgpack:"goarch"`
}

// WinDisksNats is sent by the agent on NATS subject "agent-disks".
type WinDisksNats struct {
	Agentid string        `msgpack:"id"`
	Disks   []interface{} `msgpack:"disks"`
}

// WinSvcNats is sent by the agent on NATS subject "agent-winsvc".
type WinSvcNats struct {
	Agentid string        `msgpack:"id"`
	WinSvcs []interface{} `msgpack:"svcs"`
}

// WinWMINats is sent by the agent on NATS subject "agent-wmi".
// NOTE (T023): verify msgpack tags against integration-contracts.md CONTRACT-01 before finalizing.
type WinWMINats struct {
	Agentid string                 `msgpack:"id"`
	WMI     map[string]interface{} `msgpack:"wmi"`
}
