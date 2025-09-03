package loadbalancer

import (
	"math"

	"github.com/Pranshu258/OpenPrequal/pkg/registry"
)

// LeastRequestsInFlightLoadBalancer selects backend with least requests in flight

type LeastRequestsInFlightLoadBalancer struct {
	Registry registry.BackendRegistry
}

func NewLeastRequestsInFlightLoadBalancer(reg registry.BackendRegistry) *LeastRequestsInFlightLoadBalancer {
	return &LeastRequestsInFlightLoadBalancer{Registry: reg}
}

func (lb *LeastRequestsInFlightLoadBalancer) PickBackend() string {
	backends := lb.Registry.ListBackends()
	if len(backends) == 0 {
		return ""
	}
	minIdx := -1
	minVal := int64(math.MaxInt64)
	for i, b := range backends {
		if b.RequestsInFlight < minVal {
			minVal = b.RequestsInFlight
			minIdx = i
		}
	}
	if minIdx == -1 {
		return backends[0].URL
	}
	return backends[minIdx].URL
}
