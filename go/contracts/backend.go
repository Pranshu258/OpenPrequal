package contracts

type Backend struct {
	URL              string  `json:"url"`
	Port             *int    `json:"port,omitempty"`
	Health           bool    `json:"health"`
	InFlightRequests float64 `json:"in_flight_requests"`
	AvgLatency       float64 `json:"avg_latency"`
}

func NewBackend(url string, port *int) *Backend {
	return &Backend{URL: url, Port: port, Health: false}
}

func (b *Backend) Equal(other *Backend) bool {
	if other == nil {
		return false
	}
	if b.URL != other.URL {
		return false
	}
	if (b.Port == nil) != (other.Port == nil) {
		return false
	}
	if b.Port != nil && other.Port != nil && *b.Port != *other.Port {
		return false
	}
	return true
}

// ModelDump returns a map similar to the Python model_dump() used elsewhere.
func (b *Backend) ModelDump() map[string]interface{} {
	var port interface{} = nil
	if b.Port != nil {
		port = *b.Port
	}
	return map[string]interface{}{
		"url":                b.URL,
		"port":               port,
		"health":             b.Health,
		"in_flight_requests": b.InFlightRequests,
		"avg_latency":        b.AvgLatency,
	}
}
