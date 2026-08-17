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

// --- Feature 037 · el estado de cifrado de disco, dentro de "agent-wmi" ---
//
// 🪤 Estos tres tipos son ESPEJO EXACTO de observer-agent/shared/types.go: las
// claves `json:` son el contrato y un desalineo NO da error, deja los campos en
// cero. Y acá el cero miente peor que en cualquier otro payload del archivo: un
// `protection_status` que llega en 0 por un tag mal escrito se persiste como
// "volumen SIN CIFRAR" y el panel de cumplimiento afirma algo falso sobre un
// equipo que quizá sí está cifrado. El guardián que lo vigila es la subprueba
// "agent-wmi" de TestExistingCheckinsDecodeIntact (geolocation_test.go).
//
// Por qué hay un tipo aparte y no se lee del mapa: WinWMINats.WMI es
// map[string]interface{} porque el blob se guarda entero en wmi_detail sin
// mirarlo. Para PERSISTIR en tablas propias hace falta el dato tipado, y sacarlo
// del mapa a mano —cast a map[string]interface{}, después a float64, después a
// uint32— es justo donde se pierden los nulos: un puntero nulo y un cero se
// vuelven indistinguibles en cuanto pasan por interface{}. El decode tipado los
// conserva.

// DiskEncryptionVolume es el estado de cifrado de UN volumen.
//
// Los punteros distinguen "no se pudo leer" de un cero legítimo, y esa distinción
// es la feature entera (RF-07, RN-A03):
//
//   - DriveLetter nulo: el volumen no tiene letra. Normal, y nunca es el de sistema.
//   - EncryptionPercentage nulo: el avance no se pudo leer. NO es 0 %.
//   - KeyProtectorCount nulo: no se pudo contar. NO es "cero protectores".
type DiskEncryptionVolume struct {
	DeviceID                         string   `json:"device_id"`
	DriveLetter                      *string  `json:"drive_letter"`
	ProtectionStatus                 uint32   `json:"protection_status"`
	ConversionStatus                 uint32   `json:"conversion_status"`
	EncryptionMethod                 uint32   `json:"encryption_method"`
	PersistentVolumeID               string   `json:"persistent_volume_id"`
	IsVolumeInitializedForProtection bool     `json:"is_volume_initialized_for_protection"`
	EncryptionPercentage             *uint32  `json:"encryption_percentage"`
	VolumeType                       uint32   `json:"volume_type"`
	IsSystemVolume                   bool     `json:"is_system_volume"`
	KeyProtectorCount                *int     `json:"key_protector_count"`
	KeyProtectorTypes                []uint32 `json:"key_protector_types"`
}

// DiskEncryption es el sobre que viaja bajo la clave "disk_encryption".
//
// Tres campos para tres estados que se parecen y no lo son: el equipo no ofrece
// BitLocker (Soportado=false), la consulta falló (Error != nil) o no hay
// volúmenes cifrables (Volumenes vacío, resultado legítimo). Ninguno se persiste
// como "sin cifrar".
type DiskEncryption struct {
	Soportado bool                   `json:"soportado"`
	Error     *string                `json:"error"`
	Volumenes []DiskEncryptionVolume `json:"volumenes"`
}

// WinWMIDiskEncryptionNats es el MISMO mensaje "agent-wmi", decodificado una
// segunda vez para sacar el bloque de cifrado tipado.
//
// El puntero nulo es la señal de RN-A03 y no un caso de borde: un agente
// anterior a 2.15.30 no manda `disk_encryption`, y ahí "sin dato" tiene que ser
// **ausencia de fila**, no una fila que afirme que el equipo no está cifrado.
type WinWMIDiskEncryptionNats struct {
	Agentid string `json:"agent_id"`
	WMI     struct {
		DiskEncryption *DiskEncryption `json:"disk_encryption"`
	} `json:"wmi"`
}
