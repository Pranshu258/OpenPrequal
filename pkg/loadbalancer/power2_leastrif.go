package loadbalancer

import (
	"math/rand"

	"github.com/Pranshu258/OpenPrequal/pkg/registry"
)

// PowerOfTwoLeastRIFLoadBalancer selects two random backends and picks the one with least requests in flight

type PowerOfTwoLeastRIFLoadBalancer struct {
	Registry registry.BackendRegistry
}

func NewPowerOfTwoLeastRIFLoadBalancer(reg registry.BackendRegistry) *PowerOfTwoLeastRIFLoadBalancer {
	return &PowerOfTwoLeastRIFLoadBalancer{Registry: reg}
}

func (lb *PowerOfTwoLeastRIFLoadBalancer) PickBackend() string {
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
	if b1.RequestsInFlight <= b2.RequestsInFlight {
		return b1.URL
	}
	return b2.URL
}
