package main

import (
	"encoding/json"
	"log"
	"net/http"
	"os"
	"strconv"

	"openprequal/config"
	"openprequal/contracts"
	"openprequal/core"
)

func main() {
	// create metrics manager (no rif bins)
	metrics := core.NewMetricsManager(nil)

	// backend config from package config
	cfg := config.NewFromEnv()
	url := cfg.BackendURL
	port, _ := strconv.Atoi(cfg.BackendPort)

	backend := &contracts.Backend{URL: url, Port: &port, Health: true}

	hb := core.NewHeartbeatClient(backend, cfg.ProxyURL, cfg.HeartbeatSeconds, metrics)
	hb.Start()
	defer hb.Stop()

	http.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.Header().Set("X-Backend-Id", url)
		resp := map[string]string{"message": "Hello from backend at " + url + "!"}
		_ = json.NewEncoder(w).Encode(resp)
	})

	http.HandleFunc("/probe", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.Header().Set("X-Backend-Id", url)
		resp := map[string]interface{}{
			"status":             "ok",
			"in_flight_requests": metrics.GetInFlight(),
			"avg_latency":        metrics.GetAvgLatency(),
		}
		_ = json.NewEncoder(w).Encode(resp)
	})

	// Prefer explicit PORT env var (useful in some container runtimes),
	// otherwise use configured backend port so the server actually listens
	// on the same port it reports in its Backend model.
	var addr string
	if p := os.Getenv("PORT"); p != "" {
		addr = ":" + p
	} else {
		addr = ":" + cfg.BackendPort
		if addr == ":" {
			addr = ":8081"
		}
	}
	log.Printf("starting backend server on %s", addr)
	log.Fatal(http.ListenAndServe(addr, nil))
}
