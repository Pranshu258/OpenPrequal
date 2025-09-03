package loadbalancer

import (
	"math/rand"

	"github.com/Pranshu258/OpenPrequal/pkg/registry"
)

// PowerOfTwoLeastLatencyLoadBalancer selects two random backends and picks the one with least average latency

type PowerOfTwoLeastLatencyLoadBalancer struct {
	Registry registry.BackendRegistry
}

func NewPowerOfTwoLeastLatencyLoadBalancer(reg registry.BackendRegistry) *PowerOfTwoLeastLatencyLoadBalancer {
	return &PowerOfTwoLeastLatencyLoadBalancer{Registry: reg}
}

func (lb *PowerOfTwoLeastLatencyLoadBalancer) PickBackend() string {
	backends := lb.Registry.ListBackends()
	if len(backends) == 0 {
		return ""
	}
	if len(backends) == 1 {
		return backends[0].URL
	}
	idx1 := rand.Intn(len(backends))
	idx2 := rand.Intn(len(backends))
	for idx2 == idx1 {
		idx2 = rand.Intn(len(backends))
	}
	b1 := backends[idx1]
	b2 := backends[idx2]
	if b1.AverageLatencyMs <= b2.AverageLatencyMs {
		return b1.URL
	}
	return b2.URL
}
