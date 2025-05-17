// File: main.go
package main

import (
	"log"
	"net/http"
	"os"

	"github.com/gorilla/mux"
)

func main() {
	log.Println("Starting OpenPrequal sidecar proxy...")

	// Load configuration
	config := LoadConfig()

	// Initialize metrics
	InitMetrics()

	// Initialize probe manager and selection engine
	probeManager := NewProbeManager(config)
	selector := NewReplicaSelector(config, probeManager)

	// Setup HTTP server with routing
	r := mux.NewRouter()
	r.Handle("/proxy", RIFMiddleware(http.HandlerFunc(ProxyHandler(selector)))).Methods("POST")
	r.HandleFunc("/probe", ProbeHandler(probeManager)).Methods("GET")
	r.Handle("/metrics", MetricsHandler()).Methods("GET")

	httpAddr := ":8080"
	if val := os.Getenv("SIDECAR_PORT"); val != "" {
		httpAddr = ":" + val
	}

	log.Printf("Listening on %s\n", httpAddr)
	log.Fatal(http.ListenAndServe(httpAddr, r))
}
