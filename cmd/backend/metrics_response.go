package main

type MetricsResponse struct {
	InFlight         int64 `json:"in_flight"`
	AvgLatency5MinMs int64 `json:"avg_latency_5min_ms"`
}
