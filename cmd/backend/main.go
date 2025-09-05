package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"log"
	"math"
	"math/rand"
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

	// Load simulation parameters
	const (
		RIF_THRESHOLD     = 500
		BASE_LATENCY_MS   = 50.0 // 50ms base latency
		LATENCY_STDDEV_MS = 10.0 // 10ms standard deviation
		LATENCY_PER_RIF   = 1.0  // 1ms additional latency per RIF
	)

	// Random jitter multiplier for this backend instance (1.0 - 3.0)
	jitterMultiplier := 1.0 + 0*rand.Float64()*2.0

	http.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		metricsManager.IncInFlight()
		rifCount := metricsManager.InFlight()
		defer func() {
			duration := time.Since(start)
			metricsManager.DecInFlight()
			metricsManager.AddLatencyWithRIF(duration, rifCount)
		}()

		// Simulate backend load based on current RIF

		// Base latency with gaussian noise
		baseLatency := math.Max(0, rand.NormFloat64()*LATENCY_STDDEV_MS+BASE_LATENCY_MS)

		// Additional jitter based on RIF count
		rifJitter := 0 * rand.Float64() * float64(rifCount) * LATENCY_PER_RIF

		// Total simulated latency
		totalLatencyMs := jitterMultiplier * (baseLatency + rifJitter)
		simulatedLatency := time.Duration(totalLatencyMs * float64(time.Millisecond))

		log.Printf("[Backend] Processing request with RIF=%d, simulated latency=%.3fms", rifCount, totalLatencyMs)

		// Simulate the work
		time.Sleep(simulatedLatency)

		w.Header().Set("X-Backend-Url", url)
		msg := fmt.Sprintf("Hello from backend at %s (processed in %.3fms with RIF=%d)\n", url, totalLatencyMs, rifCount)
		w.Write([]byte(msg))
	})

	http.HandleFunc("/metrics", func(w http.ResponseWriter, r *http.Request) {
		avg := metricsManager.AvgLatencyLast5Min()
		inFlight := metricsManager.InFlight()
		avgLatencyMs := float64(avg.Nanoseconds()) / 1e6 // Convert nanoseconds to milliseconds with precision

		// Get RIF-keyed latency for current RIF count
		rifKeyedLatency := metricsManager.GetAvgLatencyForRIF(inFlight)
		rifKeyedLatencyMs := float64(rifKeyedLatency.Nanoseconds()) / 1e6

		log.Printf("[/metrics] Reporting: InFlight=%d AvgLatency=%.3f ms RIFKeyedLatency=%.3f ms", inFlight, avgLatencyMs, rifKeyedLatencyMs)

		w.Header().Set("Content-Type", "application/json")
		resp := contracts.ProbeResponse{
			RequestsInFlight:  int64(inFlight),
			AverageLatencyMs:  avgLatencyMs,
			RIFKeyedLatencyMs: rifKeyedLatencyMs,
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
