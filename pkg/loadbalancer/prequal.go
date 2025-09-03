package loadbalancer

import (
	"math"
	"time"

	"github.com/Pranshu258/OpenPrequal/pkg/probe"
	"github.com/Pranshu258/OpenPrequal/pkg/registry"
)

// PrequalLoadBalancer selects the cold backend with lowest latency, or if all are hot, the one with lowest RIF
// Implements LoadBalancer interface
type PrequalLoadBalancer struct {
	Registry      registry.BackendRegistry
	probeIdx      int
	lastProbeTime int64
}

func NewPrequalLoadBalancer(reg registry.BackendRegistry) *PrequalLoadBalancer {
	return &PrequalLoadBalancer{Registry: reg}
}

func (lb *PrequalLoadBalancer) PickBackend() string {
	backends := lb.Registry.ListBackends()
	n := len(backends)
	if n == 0 {
		return ""
	}

	// Probe scheduling logic: one probe every 10ms, round robin
	now := time.Now().UnixNano() / 1e6 // ms
	if now-lb.lastProbeTime >= 10 || lb.lastProbeTime == 0 {
		go func(idx int) {
			url := backends[idx%n].URL
			result, err := probe.ProbeBackend(url)
			if err == nil {
				if memReg, ok := lb.Registry.(*registry.InMemoryBackendRegistry); ok {
					if b, exists := memReg.Backends[url]; exists {
						b.RequestsInFlight = result.RequestsInFlight
						b.AverageLatencyMs = result.AverageLatencyMs
						rif := float64(result.RequestsInFlight)
						b.Probe.AddRIF(rif)
						b.HotCold = b.Probe.Status(rif)
					}
				}
			}
		}(lb.probeIdx)
		lb.probeIdx = (lb.probeIdx + 1) % n
		lb.lastProbeTime = now
	}

	// ...existing backend selection logic...
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
