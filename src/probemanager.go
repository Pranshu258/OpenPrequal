package main

import (
	"encoding/json"
	"log"
	"math/rand"
	"net/http"
	"os"
	"strconv"
	"sync"
	"time"

	"github.com/gorilla/mux"
)

type Config struct {
	ProbeRate       float64      `json:"probe_rate"`
	ProbeTimeout    time.Duration `json:"probe_timeout"`
	QRIFThreshold   float64      `json:"qrif_threshold"`
	MaxProbePool    int          `json:"max_probe_pool"`
	ReplicaList     []string     `json:"replica_list"`
}

type ProbeData struct {
	Replica   string        `json:"replica"`
	Latency   time.Duration `json:"latency"`
	RIF       int           `json:"rif"`
	Timestamp time.Time     `json:"timestamp"`
}

type ProbeManager struct {
	config     *Config
	mutex      sync.RWMutex
	probePool  map[string]ProbeData
	httpClient *http.Client
}

func NewProbeManager(cfg *Config) *ProbeManager {
	pm := &ProbeManager{
		config:    cfg,
		probePool: make(map[string]ProbeData),
		httpClient: &http.Client{Timeout: cfg.ProbeTimeout},
	}

	// Start background probing
	go pm.startProbing()

	return pm
}

func (pm *ProbeManager) startProbing() {
	ticker := time.NewTicker(time.Duration(float64(time.Second) / pm.config.ProbeRate))
	defer ticker.Stop()

	for range ticker.C {
		for _, replica := range pm.config.ReplicaList {
			go pm.sendProbe(replica)
		}
	}
}

func (pm *ProbeManager) sendProbe(replica string) {
	start := time.Now()
	resp, err := pm.httpClient.Get("http://" + replica + "/probe")
	if err != nil {
		log.Printf("Probe to %s failed: %v", replica, err)
		return
	}
	defer resp.Body.Close()

	var result ProbeData
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		log.Printf("Invalid probe response from %s: %v", replica, err)
		return
	}

	result.Replica = replica
	result.Latency = time.Since(start)
	result.Timestamp = time.Now()

	pm.mutex.Lock()
	defer pm.mutex.Unlock()
	pm.probePool[replica] = result
}

func (pm *ProbeManager) GetProbePool() []ProbeData {
	pm.mutex.RLock()
	defer pm.mutex.RUnlock()
	pool := make([]ProbeData, 0, len(pm.probePool))
	for _, probe := range pm.probePool {
		pool = append(pool, probe)
	}
	return pool
}