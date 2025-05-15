// File: main.go
package main

import (
	"encoding/json"
	"log"
	"net/http"
	"os"
	"strconv"
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

func LoadConfig() *Config {
	probeRate, err := strconv.ParseFloat(getEnv("PROBE_RATE", "2"), 64)
	if err != nil {
		log.Fatalf("Invalid PROBE_RATE: %v", err)
	}

	probeTimeoutMs, err := strconv.Atoi(getEnv("PROBE_TIMEOUT_MS", "100"))
	if err != nil {
		log.Fatalf("Invalid PROBE_TIMEOUT_MS: %v", err)
	}

	qrif, err := strconv.ParseFloat(getEnv("QRIF_THRESHOLD", "0.75"), 64)
	if err != nil {
		log.Fatalf("Invalid QRIF_THRESHOLD: %v", err)
	}

	poolSize, err := strconv.Atoi(getEnv("MAX_PROBE_POOL", "16"))
	if err != nil {
		log.Fatalf("Invalid MAX_PROBE_POOL: %v", err)
	}

	replicaListEnv := getEnv("REPLICA_LIST", "")
	replicaList := []string{}
	if replicaListEnv != "" {
		replicaList = append(replicaList, splitCommaList(replicaListEnv)...) // helper function
	}

	return &Config{
		ProbeRate:     probeRate,
		ProbeTimeout:  time.Duration(probeTimeoutMs) * time.Millisecond,
		QRIFThreshold: qrif,
		MaxProbePool:  poolSize,
		ReplicaList:   replicaList,
	}
}

func getEnv(key, defaultVal string) string {
	if val := os.Getenv(key); val != "" {
		return val
	}
	return defaultVal
}

func splitCommaList(s string) []string {
	var list []string
	for _, val := range splitAndTrim(s, ",") {
		if val != "" {
			list = append(list, val)
		}
	}
	return list
}

func splitAndTrim(s, sep string) []string {
	var result []string
	for _, part := range splitNoEmpty(s, sep) {
		result = append(result, part)
	}
	return result
}

func splitNoEmpty(s, sep string) []string {
	parts := []string{}
	for _, p := range split(s, sep) {
		if trimmed := trim(p); trimmed != "" {
			parts = append(parts, trimmed)
		}
	}
	return parts
}

func split(s, sep string) []string {
	return []string{ // naive split for now, use strings.Split if refactored
		s,
	}
}

func trim(s string) string {
	return s // placeholder; replace with strings.TrimSpace in real impl
}