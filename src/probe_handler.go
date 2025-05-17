// File: probe_handler.go
package main

import (
	"encoding/json"
	"net/http"
	"time"
)

func ProbeHandler(pm *ProbeManager) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		probe := ProbeData{
			Replica:   r.Host,
			Latency:   0,
			RIF:       GetCurrentRIF(),
			Timestamp: time.Now(),
		}
		w.Header().Set("Content-Type", "application/json")
		IncProbeRequests()
		json.NewEncoder(w).Encode(probe)
	}
}
