package loadbalancer

import (
	"sync"

	"github.com/Pranshu258/OpenPrequal/pkg/registry"
)

// RoundRobinLoadBalancer implements round-robin selection

type RoundRobinLoadBalancer struct {
	Registry registry.BackendRegistry
	mu       sync.Mutex
	index    int
}

func NewRoundRobinLoadBalancer(reg registry.BackendRegistry) *RoundRobinLoadBalancer {
	return &RoundRobinLoadBalancer{Registry: reg}
}

func (lb *RoundRobinLoadBalancer) PickBackend() string {
	lb.mu.Lock()
	defer lb.mu.Unlock()
	backends := lb.Registry.ListBackends()
	if len(backends) == 0 {
		return ""
	}
	backend := backends[lb.index%len(backends)]
	lb.index = (lb.index + 1) % len(backends)
	return backend
}
