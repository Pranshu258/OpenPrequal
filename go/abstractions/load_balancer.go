package abstractions

import (
	"openprequal/contracts"
	"sync"
)

// LoadBalancer selects backends from a registry.
type LoadBalancer interface {
	// NextBackend returns the next backend or nil if none available.
	NextBackend() *contracts.Backend
}

// RoundRobinLoadBalancer selects backends in a round-robin fashion.
type RoundRobinLoadBalancer struct {
	reg   Registry
	mu    sync.Mutex
	index int
}

// NewRoundRobin creates a new round-robin load balancer using the provided registry.
func NewRoundRobin(reg Registry) *RoundRobinLoadBalancer {
	return &RoundRobinLoadBalancer{reg: reg}
}

// NextBackend returns the next backend URL in round-robin order, or nil if none.
func (r *RoundRobinLoadBalancer) NextBackend() *contracts.Backend {
	r.mu.Lock()
	defer r.mu.Unlock()
	backends := r.reg.ListBackends()
	if len(backends) == 0 {
		return nil
	}
	b := backends[r.index%len(backends)]
	r.index = (r.index + 1) % len(backends)
	return &b
}
