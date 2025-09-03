package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"time"

	"github.com/Pranshu258/OpenPrequal/pkg/contracts"
	"github.com/Pranshu258/OpenPrequal/pkg/metrics"
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

	metricsManager := metrics.NewMetricsManager()

	http.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		metricsManager.IncInFlight()
		defer func() {
			metricsManager.DecInFlight()
			metricsManager.AddLatency(time.Since(start))
		}()

		w.Header().Set("X-Backend-Url", url)
		msg := fmt.Sprintf("Hello from backend at %s\n", url)
		w.Write([]byte(msg))
	})

	http.HandleFunc("/metrics", func(w http.ResponseWriter, r *http.Request) {
		avg := metricsManager.AvgLatencyLast5Min()
		inFlight := metricsManager.InFlight()
		avgLatencyMs := float64(avg.Nanoseconds()) / 1e6 // Convert nanoseconds to milliseconds with precision

		log.Printf("[/metrics] Reporting: InFlight=%d AvgLatency=%.3f ms", inFlight, avgLatencyMs)

		w.Header().Set("Content-Type", "application/json")
		resp := contracts.ProbeResponse{
			RequestsInFlight: int64(inFlight),
			AverageLatencyMs: avgLatencyMs,
		}
		json.NewEncoder(w).Encode(resp)
	})

	// Heartbeat goroutine to register with proxy
	proxyAddr := os.Getenv("PROXY_ADDR")
	if proxyAddr == "" {
		proxyAddr = "http://localhost:8080"
	}
	go func() {
		for {
			reqBody := map[string]string{"url": url}
			data, err := json.Marshal(reqBody)
			if err != nil {
				log.Printf("Heartbeat marshal error: %v", err)
				time.Sleep(5 * time.Second)
				continue
			}
			resp, err := http.Post(proxyAddr+"/heartbeat", "application/json", bytes.NewReader(data))
			if err != nil {
				log.Printf("Heartbeat failed: %v", err)
			} else {
				resp.Body.Close()
			}
			time.Sleep(5 * time.Second)
		}
	}()

	log.Printf("Backend server listening at %s\n", url)
	if err := http.ListenAndServe(":"+port, nil); err != nil {
		log.Fatalf("Server failed: %v", err)
	}
}
