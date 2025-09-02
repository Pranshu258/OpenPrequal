package loadbalancer

import (
	"math/rand"

	"github.com/Pranshu258/OpenPrequal/cmd/proxy/internal/registry"
)

// RandomLoadBalancer implements the random selection strategy

type RandomLoadBalancer struct {
	Registry registry.BackendRegistry
}

func NewRandomLoadBalancer(reg registry.BackendRegistry) *RandomLoadBalancer {
	return &RandomLoadBalancer{Registry: reg}
}

func (lb *RandomLoadBalancer) PickBackend() string {
	backends := lb.Registry.ListBackends()
	if len(backends) == 0 {
		return ""
	}
	return backends[rand.Intn(len(backends))]
}
