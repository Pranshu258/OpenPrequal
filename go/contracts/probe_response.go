package contracts

type ProbeResponse struct {
	Status           string  `json:"status"`
	InFlightRequests int     `json:"in_flight_requests"`
	AvgLatency       float64 `json:"avg_latency"`
}
