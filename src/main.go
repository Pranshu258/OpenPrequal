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

	// Initialize probe manager and selection engine
	probeManager := NewProbeManager(config)
	selector := NewReplicaSelector(config, probeManager)

	// Setup HTTP server with routing
	r := mux.NewRouter()
	r.Use(RIFMiddleware) // Middleware to track requests in flight
	r.HandleFunc("/proxy", ProxyHandler(selector)).Methods("POST")
	r.HandleFunc("/probe", ProbeHandler(probeManager)).Methods("GET")

	httpAddr := ":8080"
	if val := os.Getenv("SIDECAR_PORT"); val != "" {
		httpAddr = ":" + val
	}

	log.Printf("Listening on %s\n", httpAddr)
	log.Fatal(http.ListenAndServe(httpAddr, r))
}

// TODOs (to be implemented in other files):
// - NewProbeManager(): manages async probing of replicas
// - NewReplicaSelector(): implements HCL selection rule
// - ProxyHandler(): accepts incoming requests and forwards to selected replica
// - ProbeHandler(): serves as the endpoint for other sidecars to probe this instance
