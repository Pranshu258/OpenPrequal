package loadbalancer

import (
	"math"

	"github.com/Pranshu258/OpenPrequal/pkg/registry"
)

// LeastLatencyLoadBalancer selects backend with least average latency

type LeastLatencyLoadBalancer struct {
	Registry registry.BackendRegistry
}

func NewLeastLatencyLoadBalancer(reg registry.BackendRegistry) *LeastLatencyLoadBalancer {
	return &LeastLatencyLoadBalancer{Registry: reg}
}

func (lb *LeastLatencyLoadBalancer) PickBackend() string {
	backends := lb.Registry.ListBackends()
	if len(backends) == 0 {
		return ""
	}
	minIdx := -1
	minVal := math.MaxFloat64
	for i, b := range backends {
		if b.AverageLatencyMs < minVal {
			minVal = b.AverageLatencyMs
			minIdx = i
		}
	}
	if minIdx == -1 {
		return backends[0].URL
	}
	return backends[minIdx].URL
}
