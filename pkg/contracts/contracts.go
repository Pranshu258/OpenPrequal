package contracts

type HeartbeatRequest struct {
	URL string `json:"url"`
}

type ProbeResponse struct {
	RequestsInFlight  int64   `json:"requests_in_flight"`
	AverageLatencyMs  float64 `json:"average_latency_ms"`
	RIFKeyedLatencyMs float64 `json:"rif_keyed_latency_ms"`
}
