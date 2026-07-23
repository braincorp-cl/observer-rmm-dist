package shared

// GAP-051: el agente (observer-agent, canónico) serializa los payloads NATS con
// github.com/ugorji/go/codec, cuyo MsgpackHandle por defecto honra los tags "codec"
// y luego "json" (helper.go: NewTypeInfos([]string{"codec","json"})) e IGNORA "msgpack".
// Estos structs deben usar tags `json:` con claves IDÉNTICAS a las del agente
// (observer-agent/shared/types.go), o el decode produce structs vacíos (Agentid="")
// y los UPDATE ... WHERE agent_id='' no matchean ninguna fila → sin last_seen ni
// inventario. (Antes usaban `msgpack:` → ugorji caía al nombre del campo Go y nada
// matcheaba. Mismo formato de wire para Windows y Linux: un solo shared/types.go y un
// solo NatsMessage sin build-tags. Cierra el TODO T023 de CONTRACT-01.)

// CheckInNats is sent by the agent on NATS subject "agent-hello".
type CheckInNats struct {
	Agentid string `json:"agent_id"`
	Version string `json:"version"`
}

// PublicIPNats is sent by the agent on NATS subject "agent-publicip".
type PublicIPNats struct {
	Agentid  string `json:"agent_id"`
	PublicIP string `json:"public_ip"`
}

// GeoNats is sent by the agent on NATS subject "agent-geolocation".
// Espejo EXACTO de observer-agent/shared/types.go#GeoNats: mismas claves de
// wire `json:` (GAP-051). Cambiar una clave aquí sin cambiarla en el agente
// rompe el decode silenciosamente (struct vacío → INSERT sin agente). Ver
// CONTRACT-01 (023-geolocalizacion-agente).
type GeoNats struct {
	Func       string  `json:"func"`
	Agentid    string  `json:"agent_id"`
	Version    string  `json:"version"`
	Lat        float64 `json:"lat"`
	Long       float64 `json:"long"`
	AccuracyM  int     `json:"accuracy_m"`
	Source     string  `json:"source"`
	CapturedAt int64   `json:"captured_at"`
}

// AgentInfoNats is sent by the agent on NATS subject "agent-agentinfo".
type AgentInfoNats struct {
	Agentid      string  `json:"agent_id"`
	Hostname     string  `json:"hostname"`
	OS           string  `json:"operating_system"`
	Platform     string  `json:"plat"`
	TotalRAM     float64 `json:"total_ram"`
	BootTime     int64   `json:"boot_time"`
	RebootNeeded bool    `json:"needs_reboot"`
	Username     string  `json:"logged_in_username"`
	GoArch       string  `json:"goarch"`
}

// WinDisksNats is sent by the agent on NATS subject "agent-disks".
type WinDisksNats struct {
	Agentid string        `json:"agent_id"`
	Disks   []interface{} `json:"disks"`
}

// WinSvcNats is sent by the agent on NATS subject "agent-winsvc".
type WinSvcNats struct {
	Agentid string        `json:"agent_id"`
	WinSvcs []interface{} `json:"services"`
}

// WinWMINats is sent by the agent on NATS subject "agent-wmi".
type WinWMINats struct {
	Agentid string                 `json:"agent_id"`
	WMI     map[string]interface{} `json:"wmi"`
}
