package loadbalancer

import (
	"log"
	"math"
	"math/rand"
	"sync"
	"time"

	"github.com/Pranshu258/OpenPrequal/pkg/metrics"
	"github.com/Pranshu258/OpenPrequal/pkg/probe"
	"github.com/Pranshu258/OpenPrequal/pkg/registry"
)

// PrequalLoadBalancer selects the cold backend with lowest latency, or if all are hot, the one with lowest RIF
// Implements LoadBalancer interface
type PrequalLoadBalancer struct {
	Registry          registry.BackendRegistry
	probeQueue        chan string
	stopProbe         chan struct{}
	probeHistory      map[string]struct{}
	lastProbeTime     map[string]int64
	requestTimestamps []int64
	mu                sync.Mutex
	wg                sync.WaitGroup
	rand              *rand.Rand
}

func NewPrequalLoadBalancer(reg registry.BackendRegistry) *PrequalLoadBalancer {
	lb := &PrequalLoadBalancer{
		Registry:          reg,
		probeQueue:        make(chan string, 100),
		stopProbe:         make(chan struct{}),
		probeHistory:      make(map[string]struct{}),
		lastProbeTime:     make(map[string]int64),
		requestTimestamps: make([]int64, 0, 1000),
		rand:              rand.New(rand.NewSource(time.Now().UnixNano())),
	}
	lb.startProbeScheduler()
	return lb
}

func (lb *PrequalLoadBalancer) PickBackend() string {
	backends := lb.Registry.ListBackends()
	n := len(backends)
	if n == 0 {
		log.Println("[Prequal] No backends available.")
		return ""
	}

	// append request timestamp under lock
	now := time.Now().UnixNano() / 1e9 // seconds
	lb.mu.Lock()
	lb.requestTimestamps = append(lb.requestTimestamps, now)
	window := int64(1)
	cutoff := now - window
	for len(lb.requestTimestamps) > 0 && lb.requestTimestamps[0] < cutoff {
		lb.requestTimestamps = lb.requestTimestamps[1:]
	}
	lb.mu.Unlock()

	log.Printf("[Prequal] Backend info snapshot:")
	for i, b := range backends {
		log.Printf("  [%d] URL=%s HotCold=%s AvgLatency=%.6f RIFKeyedLatency=%.6f RIF=%d", i, b.URL, b.HotCold, b.AverageLatencyMs, b.RIFKeyedLatencyMs, b.RequestsInFlight)
	}

	coldIndices := []int{}
	coldLatency := math.MaxFloat64
	allHot := true

	for i, b := range backends {
		if b.HotCold == "cold" {
			allHot = false
			// Use RIF-keyed latency instead of average latency
			rifKeyedLatency := b.RIFKeyedLatencyMs
			if rifKeyedLatency < coldLatency {
				coldLatency = rifKeyedLatency
				coldIndices = []int{i}
			} else if rifKeyedLatency == coldLatency {
				coldIndices = append(coldIndices, i)
			}
		}
	}

	if !allHot && len(coldIndices) > 0 {
		// select among cold backends
		sel := coldIndices[0]
		if len(coldIndices) > 1 {
			sel = coldIndices[lb.rand.Intn(len(coldIndices))]
		}
		log.Printf("[Prequal] Selected cold backend: %s (RIF-keyed latency=%.6f)", backends[sel].URL, backends[sel].RIFKeyedLatencyMs)
		return backends[sel].URL
	}

	// If all are hot, pick backend with lowest RequestsInFlight
	minRIF := math.MaxFloat64
	minRIFIndices := []int{}
	for i, b := range backends {
		rif := float64(b.RequestsInFlight)
		if rif < minRIF {
			minRIF = rif
			minRIFIndices = []int{i}
		} else if rif == minRIF {
			minRIFIndices = append(minRIFIndices, i)
		}
	}
	if len(minRIFIndices) > 0 {
		// select among hot backends with minimal RIF
		sel := minRIFIndices[0]
		if len(minRIFIndices) > 1 {
			sel = minRIFIndices[lb.rand.Intn(len(minRIFIndices))]
		}
		log.Printf("[Prequal] Selected hot backend: %s (RIF=%d)", backends[sel].URL, backends[sel].RequestsInFlight)
		return backends[sel].URL
	}
	idx := 0
	if n > 1 {
		idx = lb.rand.Intn(n)
	}
	log.Printf("[Prequal] Fallback: returning random backend: %s", backends[idx].URL)
	return backends[idx].URL
}

// startProbeScheduler starts a background goroutine that schedules and consumes probe tasks
func (lb *PrequalLoadBalancer) startProbeScheduler() {
	lb.wg.Add(1)
	go func() {
		defer lb.wg.Done()
		for {
			select {
			case <-lb.stopProbe:
				return
			default:
				backends := lb.Registry.ListBackends()
				healthy := make([]string, 0, len(backends))
				for _, b := range backends {
					if b.HotCold != "" { // treat non-empty HotCold as healthy
						healthy = append(healthy, b.URL)
					}
				}
				now := time.Now().UnixNano() / 1e9 // seconds
				// Forced probe: every backend at least once every 20s
				minProbeInterval := int64(20)
				lb.mu.Lock()
				for _, url := range healthy {
					last := lb.lastProbeTime[url]
					if now-last >= minProbeInterval {
						lb.lastProbeTime[url] = now
						select {
						case lb.probeQueue <- url:
							log.Printf("[Prequal] Forced probe scheduled for backend: %s", url)
						default:
							log.Printf("[Prequal] Probe queue full, dropping forced probe for backend: %s", url)
						}
					}
				}
				lb.mu.Unlock()

				// RPS-based probabilistic probe
				window := int64(1) // 1 second window for RPS
				lb.mu.Lock()
				count := 0
				cutoff := now - window
				for _, ts := range lb.requestTimestamps {
					if ts >= cutoff {
						count++
					}
				}
				lb.mu.Unlock()
				rps := float64(count)
				if rps < 1e-6 {
					rps = 1e-6
				}
				R := 5.0 / rps
				if R > 1.0 {
					R = 1.0
				}

				// Without replacement
				lb.mu.Lock()
				available := make([]string, 0, len(healthy))
				for _, url := range healthy {
					if _, seen := lb.probeHistory[url]; !seen {
						available = append(available, url)
					}
				}
				if len(available) == 0 {
					lb.probeHistory = make(map[string]struct{})
					available = healthy
				}
				if len(available) > 0 && lb.rand.Float64() < R {
					idx2 := lb.rand.Intn(len(available))
					url := available[idx2]
					lb.probeHistory[url] = struct{}{}
					lb.lastProbeTime[url] = now
					select {
					case lb.probeQueue <- url:
						log.Printf("[Prequal] Probabilistic probe scheduled for backend: %s (R=%.3f, RPS=%.6f)", url, R, rps)
					default:
						log.Printf("[Prequal] Probe queue full, dropping probabilistic probe for backend: %s", url)
					}
				}
				lb.mu.Unlock()

				// Consume probe tasks, then pause briefly
			consumeLoop:
				for {
					select {
					case url := <-lb.probeQueue:
						result, err := probe.ProbeBackend(url)
						if err == nil {
							if memReg, ok := lb.Registry.(*registry.InMemoryBackendRegistry); ok {
								if b, exists := memReg.Backends[url]; exists {
									b.RequestsInFlight = result.RequestsInFlight
									b.AverageLatencyMs = result.AverageLatencyMs
									b.RIFKeyedLatencyMs = result.RIFKeyedLatencyMs
									rif := float64(result.RequestsInFlight)
									b.Probe.AddRIF(rif)
									b.HotCold = b.Probe.Status(rif)
									log.Printf("[Prequal] Probe updated backend: %s AvgLatency=%.6f RIFKeyedLatency=%.6f RIF=%d HotCold=%s", url, b.AverageLatencyMs, b.RIFKeyedLatencyMs, b.RequestsInFlight, b.HotCold)
									metrics.LogProbeUpdate(url, b.RequestsInFlight, b.AverageLatencyMs, b.RIFKeyedLatencyMs, b.HotCold)
								}
							}
						} else {
							log.Printf("[Prequal] Probe failed for backend: %s, err: %v", url, err)
						}
					default:
						// Exit inner loop and continue scheduling
						time.Sleep(20 * time.Millisecond)
						break consumeLoop
					}
				}
			}
		}
	}()
}

// Stop gracefully shuts down the probe scheduler
func (lb *PrequalLoadBalancer) Stop() {
	close(lb.stopProbe)
	lb.wg.Wait()
}
