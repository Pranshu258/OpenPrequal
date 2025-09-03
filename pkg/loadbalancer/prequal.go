package loadbalancer

import (
	"math"

	"github.com/Pranshu258/OpenPrequal/pkg/registry"
)

// PrequalLoadBalancer selects the cold backend with lowest latency, or if all are hot, the one with lowest RIF
// Implements LoadBalancer interface

type PrequalLoadBalancer struct {
	Registry registry.BackendRegistry
}

func NewPrequalLoadBalancer(reg registry.BackendRegistry) *PrequalLoadBalancer {
	return &PrequalLoadBalancer{Registry: reg}
}

func (lb *PrequalLoadBalancer) PickBackend() string {
	backends := lb.Registry.ListBackends()
	if len(backends) == 0 {
		return ""
	}

	coldIdx := -1
	coldLatency := math.MaxFloat64
	allHot := true

	for i, b := range backends {
		if b.HotCold == "cold" {
			allHot = false
			if b.AverageLatencyMs < coldLatency {
				coldLatency = b.AverageLatencyMs
				coldIdx = i
			}
		}
	}

	if !allHot && coldIdx != -1 {
		return backends[coldIdx].URL
	}

	// If all are hot, pick backend with lowest RequestsInFlight
	minRIF := math.MaxFloat64
	minRIFIdx := -1
	for i, b := range backends {
		rif := float64(b.RequestsInFlight)
		if rif < minRIF {
			minRIF = rif
			minRIFIdx = i
		}
	}
	if minRIFIdx != -1 {
		return backends[minRIFIdx].URL
	}
	return backends[0].URL
}
