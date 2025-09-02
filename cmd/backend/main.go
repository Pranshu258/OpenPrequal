package main

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"time"
)

func main() {
	port := os.Getenv("PORT")
	if port == "" {
		port = "8081" // default port
	}
	host := os.Getenv("HOST")
	if host == "" {
		host = "localhost"
	}
	url := fmt.Sprintf("http://%s:%s", host, port)

	metrics := NewMetricsManager()

	http.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		metrics.IncInFlight()
		defer func() {
			metrics.DecInFlight()
			metrics.AddLatency(time.Since(start))
		}()

		w.Header().Set("X-Backend-Url", url)
		msg := fmt.Sprintf("Hello from backend at %s\n", url)
		w.Write([]byte(msg))
	})

	http.HandleFunc("/metrics", func(w http.ResponseWriter, r *http.Request) {
		avg := metrics.AvgLatencyLast5Min()
		inFlight := metrics.InFlight()
		w.Header().Set("Content-Type", "application/json")
		resp := MetricsResponse{
			InFlight:         int64(inFlight),
			AvgLatency5MinMs: avg.Milliseconds(),
		}
		json.NewEncoder(w).Encode(resp)
	})

	log.Printf("Backend server listening at %s\n", url)
	if err := http.ListenAndServe(":"+port, nil); err != nil {
		log.Fatalf("Server failed: %v", err)
	}
}
