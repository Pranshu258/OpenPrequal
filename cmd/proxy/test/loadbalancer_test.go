package test

import (
	"testing"

	"github.com/Pranshu258/OpenPrequal/cmd/proxy/internal/loadbalancer"
	"github.com/Pranshu258/OpenPrequal/cmd/proxy/internal/registry"
)

func TestRandomLoadBalancer_PickBackend(t *testing.T) {
	backends := []string{"http://localhost:8081", "http://localhost:8082"}
	reg := registry.NewInMemoryBackendRegistry(backends)
	lb := loadbalancer.NewRandomLoadBalancer(reg)
	picked := lb.PickBackend()
	found := false
	for _, b := range backends {
		if picked == b {
			found = true
			break
		}
	}
	if !found {
		t.Errorf("PickBackend() = %v, want one of %v", picked, backends)
	}
}

func TestRoundRobinLoadBalancer_PickBackend(t *testing.T) {
	backends := []string{"http://localhost:8081", "http://localhost:8082"}
	reg := registry.NewInMemoryBackendRegistry(backends)
	lb := loadbalancer.NewRoundRobinLoadBalancer(reg)
	first := lb.PickBackend()
	second := lb.PickBackend()
	third := lb.PickBackend()
	if first != backends[0] || second != backends[1] || third != backends[0] {
		t.Errorf("RoundRobin sequence incorrect: got %v, %v, %v; want %v, %v, %v", first, second, third, backends[0], backends[1], backends[0])
	}
}
