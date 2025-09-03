package main

import (
	"encoding/json"
	"log"
	"net/http"
	"net/http/httputil"
	"net/url"
	"os"
	"time"

	"github.com/Pranshu258/OpenPrequal/pkg/contracts"
	"github.com/Pranshu258/OpenPrequal/pkg/loadbalancer"
	"github.com/Pranshu258/OpenPrequal/pkg/probe"
	"github.com/Pranshu258/OpenPrequal/pkg/registry"
)

// getLoadBalancerType returns the load balancer type from env/config, defaulting to "random"
func getLoadBalancerType() string {
	typeFromEnv := os.Getenv("LOAD_BALANCER_TYPE")
	if typeFromEnv != "" {
		return typeFromEnv
	}
	return "random"
}

func createLoadBalancer(reg registry.BackendRegistry, lbType string) loadbalancer.LoadBalancer {
	switch lbType {
	case "random":
		return loadbalancer.NewRandomLoadBalancer(reg)
	case "roundrobin":
		return loadbalancer.NewRoundRobinLoadBalancer(reg)
	case "leastrif":
		return loadbalancer.NewLeastRequestsInFlightLoadBalancer(reg)
	case "leastlatency":
		return loadbalancer.NewLeastLatencyLoadBalancer(reg)
	case "power2_leastrif":
		return loadbalancer.NewPowerOfTwoLeastRIFLoadBalancer(reg)
	case "power2_leastlatency":
		return loadbalancer.NewPowerOfTwoLeastLatencyLoadBalancer(reg)
	default:
		return loadbalancer.NewRandomLoadBalancer(reg)
	}
}

// getRegistryType returns the registry type from env/config, defaulting to "inmemory"
func getRegistryType() string {
	typeFromEnv := os.Getenv("REGISTRY_TYPE")
	if typeFromEnv != "" {
		return typeFromEnv
	}
	return "inmemory"
}

func createRegistry(regType string) registry.BackendRegistry {
	backendUrlsEnv := os.Getenv("BACKEND_URLS")
	var backends []string
	if backendUrlsEnv != "" {
		// Split comma-separated URLs
		for _, url := range splitAndTrim(backendUrlsEnv, ",") {
			if url != "" {
				backends = append(backends, url)
			}
		}
	} else {
		backends = []string{
			"http://localhost:8081",
			"http://localhost:8082",
			"http://localhost:8083",
		}
	}

	switch regType {
	case "inmemory":
		return registry.NewInMemoryBackendRegistry(backends)
	// case "redis":
	//     return registry.NewRedisBackendRegistry(...)
	default:
		return registry.NewInMemoryBackendRegistry(backends)
	}
}

// splitAndTrim splits a string by sep and trims spaces from each part
func splitAndTrim(s, sep string) []string {
	var result []string
	for _, part := range split(s, sep) {
		trimmed := trim(part)
		result = append(result, trimmed)
	}
	return result
}

func split(s, sep string) []string {
	var result []string
	start := 0
	for i := 0; i < len(s); i++ {
		if string(s[i]) == sep {
			result = append(result, s[start:i])
			start = i + 1
		}
	}
	result = append(result, s[start:])
	return result
}

func trim(s string) string {
	start := 0
	end := len(s)
	for start < end && (s[start] == ' ' || s[start] == '\t' || s[start] == '\n') {
		start++
	}
	for end > start && (s[end-1] == ' ' || s[end-1] == '\t' || s[end-1] == '\n') {
		end--
	}
	return s[start:end]
}

func main() {
	regType := getRegistryType()
	reg := createRegistry(regType)

	lbType := getLoadBalancerType()
	lb := createLoadBalancer(reg, lbType)

	// Periodically probe backends and update metrics
	go func() {
		ticker := time.NewTicker(1 * time.Second)
		defer ticker.Stop()
		for {
			<-ticker.C
			// ListBackends returns []BackendInfo
			backends := reg.ListBackends()
			for _, backend := range backends {
				result, err := probe.ProbeBackend(backend.URL)
				if err != nil {
					log.Printf("Probe failed for %s: %v", backend.URL, err)
					continue
				}
				// Update metrics in registry
				// Only works for InMemoryBackendRegistry
				if memReg, ok := reg.(*registry.InMemoryBackendRegistry); ok {
					if b, exists := memReg.Backends[backend.URL]; exists {
						b.RequestsInFlight = result.RequestsInFlight
						b.AverageLatencyMs = result.AverageLatencyMs
					}
				}
			}
		}
	}()

	http.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		backendURL, err := url.Parse(lb.PickBackend())
		if err != nil {
			http.Error(w, "Bad backend URL", http.StatusInternalServerError)
			return
		}
		proxy := httputil.NewSingleHostReverseProxy(backendURL)
		proxy.ErrorHandler = func(w http.ResponseWriter, req *http.Request, e error) {
			log.Printf("Proxy error: %v", e)
			http.Error(w, "Proxy error", http.StatusBadGateway)
		}
		proxy.ServeHTTP(w, r)
	})

	// Heartbeat endpoint for backend registration
	http.HandleFunc("/heartbeat", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
			return
		}
		var reqData contracts.HeartbeatRequest
		err := json.NewDecoder(r.Body).Decode(&reqData)
		if err != nil || reqData.URL == "" {
			http.Error(w, "Invalid or missing url in JSON body", http.StatusBadRequest)
			return
		}
		reg.RegisterBackend(reqData.URL)
		log.Printf("Registered backend: %s", reqData.URL)
		w.WriteHeader(http.StatusOK)
		w.Write([]byte("ok"))
	})

	log.Println("Load balancer listening on :8080 (algorithm:", lbType, ", registry:", regType, ")")
	if err := http.ListenAndServe(":8080", nil); err != nil {
		log.Fatalf("Server failed: %v", err)
	}
}
