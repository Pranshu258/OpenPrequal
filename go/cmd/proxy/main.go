package main

import (
	"context"
	"encoding/json"
	"io"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"openprequal/abstractions"
	"openprequal/algorithms"
	"openprequal/config"
	"openprequal/contracts"
	"openprequal/core"
)

// This binary provides a proxy that uses the Prequal load balancer and the
// core proxy handler to forward requests to selected backends.
func main() {
	// Create core components
	probePool := core.NewProbePool()
	probeQueue := core.NewProbeTaskQueue()
	// Probe manager requires endpoint and maxConcurrent; use defaults here
	probeManager := core.NewProbeManager(probePool, probeQueue, "", 4)

	// Registry using the in-memory implementation
	registry := abstractions.NewInMemoryRegistry()

	// Allow selecting the load balancer implementation via env (LOAD_BALANCER_CLASS)
	// supported short keys: default|prequal, round_robin, random, least_latency,
	// least_latency_p2, least_rif, least_rif_p2
	cfg := config.NewFromEnv()
	var lb interface{ Next() *contracts.Backend }
	switch cfg.LoadBalancerClass {
	case "round_robin":
		log.Printf("using load balancer: round_robin")
		lb = algorithms.NewRoundRobin(registry)
	case "random":
		log.Printf("using load balancer: random")
		lb = algorithms.NewRandomLB(registry)
	case "least_latency":
		log.Printf("using load balancer: least_latency")
		lb = algorithms.NewLeastLatencyLB(registry)
	case "least_latency_p2":
		log.Printf("using load balancer: least_latency_p2")
		lb = algorithms.NewLeastLatencyP2(registry)
	case "least_rif":
		log.Printf("using load balancer: least_rif")
		lb = algorithms.NewLeastRIF(registry)
	case "least_rif_p2":
		log.Printf("using load balancer: least_rif_p2")
		lb = algorithms.NewLeastRIFP2(registry)
	case "default", "prequal":
		fallthrough
	default:
		log.Printf("using load balancer: prequal (default)")
		lb = algorithms.NewPrequal(registry, probePool, probeQueue)
	}

	// Create proxy handler with default http client
	proxyHandler := core.NewProxyHandler(&http.Client{})

	// Register management endpoints on default mux
	// /register - backend posts its info
	http.HandleFunc("/register", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
			return
		}
		var backend contracts.Backend
		if err := json.NewDecoder(r.Body).Decode(&backend); err != nil {
			http.Error(w, "invalid body", http.StatusBadRequest)
			return
		}
		registry.Register(backend)
		w.WriteHeader(http.StatusOK)
		json.NewEncoder(w).Encode(map[string]string{"status": "registered"})
	})

	http.HandleFunc("/unregister", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
			return
		}
		var backend contracts.Backend
		if err := json.NewDecoder(r.Body).Decode(&backend); err != nil {
			http.Error(w, "invalid body", http.StatusBadRequest)
			return
		}
		registry.Unregister(backend)
		w.WriteHeader(http.StatusOK)
		json.NewEncoder(w).Encode(map[string]string{"status": "unregistered"})
	})

	// simple /metrics endpoint for readiness checks
	http.HandleFunc("/metrics", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		w.Write([]byte("# metrics placeholder\n"))
	})

	// default proxy handler
	http.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		backend := lb.Next()
		if backend == nil {
			http.Error(w, "no backends", http.StatusServiceUnavailable)
			return
		}
		if resp, err := proxyHandler.HandleProxy(r, backend.URL); err != nil {
			http.Error(w, err.Error(), http.StatusBadGateway)
		} else {
			defer resp.Body.Close()
			w.WriteHeader(resp.StatusCode)
			_, _ = io.Copy(w, resp.Body)
		}
	})

	srv := &http.Server{Addr: ":8000", Handler: nil}

	// Start probe manager
	ctx, cancel := context.WithCancel(context.Background())
	probeManager.Run(ctx)

	// Start HTTP server
	go func() {
		log.Printf("starting proxy on %s", srv.Addr)
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("server error: %v", err)
		}
	}()

	// Wait for shutdown signal
	stop := make(chan os.Signal, 1)
	signal.Notify(stop, os.Interrupt, syscall.SIGTERM)
	<-stop

	// Shutdown
	cancel()
	ctxTimeout, cancelTimeout := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancelTimeout()
	_ = srv.Shutdown(ctxTimeout)
}
