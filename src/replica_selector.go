// File: replica_selector.go
package main

import (
	"errors"
	"sort"
	"time"
)

type ReplicaSelector struct {
	config       *Config
	probeManager *ProbeManager
}

func NewReplicaSelector(cfg *Config, pm *ProbeManager) *ReplicaSelector {
	return &ReplicaSelector{
		config:       cfg,
		probeManager: pm,
	}
}

func (rs *ReplicaSelector) SelectReplica() (string, error) {
	pool := rs.probeManager.GetProbePool()
	if len(pool) == 0 {
		return "", errors.New("no probe data available")
	}

	// Filter recent probes (e.g., within 2x probe timeout)
	cutoff := time.Now().Add(-2 * rs.config.ProbeTimeout)
	recent := make([]ProbeData, 0, len(pool))
	for _, p := range pool {
		if p.Timestamp.After(cutoff) {
			recent = append(recent, p)
		}
	}
	if len(recent) == 0 {
		return "", errors.New("no recent probe data")
	}

	// Sort using Hot-Cold Lexicographic (HCL) rule: (latency, QRIF rank)
	sort.SliceStable(recent, func(i, j int) bool {
		if recent[i].Latency != recent[j].Latency {
			return recent[i].Latency < recent[j].Latency
		}
		return recent[i].RIF < recent[j].RIF
	})

	return recent[0].Replica, nil
}
