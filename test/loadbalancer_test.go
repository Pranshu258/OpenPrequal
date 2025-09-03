package test

import (
	"testing"

	"github.com/Pranshu258/OpenPrequal/pkg/loadbalancer"
	"github.com/Pranshu258/OpenPrequal/pkg/registry"
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

// Test LeastRequestsInFlightLoadBalancer
func TestLeastRequestsInFlightLoadBalancer_PickBackend(t *testing.T) {
	reg := registry.NewInMemoryBackendRegistry([]string{"a", "b", "c"})
	reg.Backends["a"].RequestsInFlight = 5
	reg.Backends["b"].RequestsInFlight = 2
	reg.Backends["c"].RequestsInFlight = 7
	lb := loadbalancer.NewLeastRequestsInFlightLoadBalancer(reg)
	picked := lb.PickBackend()
	if picked != "b" {
		t.Errorf("LeastRequestsInFlightLoadBalancer picked %v, want 'b'", picked)
	}
}

// Test LeastLatencyLoadBalancer
func TestLeastLatencyLoadBalancer_PickBackend(t *testing.T) {
	reg := registry.NewInMemoryBackendRegistry([]string{"x", "y", "z"})
	reg.Backends["x"].AverageLatencyMs = 100.0
	reg.Backends["y"].AverageLatencyMs = 50.0
	reg.Backends["z"].AverageLatencyMs = 200.0
	lb := loadbalancer.NewLeastLatencyLoadBalancer(reg)
	picked := lb.PickBackend()
	if picked != "y" {
		t.Errorf("LeastLatencyLoadBalancer picked %v, want 'y'", picked)
	}
}
